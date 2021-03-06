import numpy as np
import gpflow
import tensorflow as tf
import tensorflow_probability as tfp


def fourier_features(X, W, b):
    """
    Given sampled tensors W and b, construct Fourier features of X. We do not take into account the normalizing constant
    alpha in this method as it is only used for optimization, and the constant does not affect the location of the
    maximizing point.
    :param X: tensor of shape (count, n, d)
    :param W: tensor of shape (count, D, d)
    :param b: tensor of shape (count, D, 1)
    :param kernel: gpflow kernel
    :return: tensor of shape (count, n, D)
    """
    D = W.shape[1]

    WX_b = W @ tf.linalg.matrix_transpose(X) + b  # (count, D, n)
    return tf.cast(tf.sqrt(2.0 / D), dtype=tf.float64) * tf.cos(tf.linalg.matrix_transpose(WX_b))  # (count, n, D)


def sample_fourier_features(X, kernel, D=100):
    """
    Fourier feature mapping of X for the RBF kernel
    :param X: tensor of shape (count, n, d)
    :return: tensor of shape (count, n, D)
    """
    count = X.shape[0]
    d = X.shape[2]

    if type(kernel) == gpflow.kernels.base.Product:  # For DTS implementation where we use a product of kernels
        input_dims = d // 2
        lengthscales = np.zeros(d)
        for i in range(input_dims):
            k = kernel.kernels[i]
            lengthscale_val = k.lengthscale.numpy()
            lengthscales[i] = lengthscale_val
            lengthscales[i + input_dims] = lengthscale_val
    else:
        lengthscales = kernel.lengthscale.numpy()

    W = tf.random.normal(shape=(count, D, d),
                         mean=0.0,
                         stddev=1.0 / lengthscales,
                         dtype=tf.float64)
    b = tf.random.uniform(shape=(count, D, 1),
                          minval=0,
                          maxval=2 * np.pi,
                          dtype=tf.float64)

    return fourier_features(X, W, b), W, b  # (count, n, D)


def sample_theta_variational(phi, q_mu, q_sqrt):
    """
    Samples from distribution q(theta|D) = /int p(theta|y)p(y|f)q(f|D) df dy
    :param phi: Fourier features tensor with shape (count, n, D)
    :param q_mu: tensor of shape (n, 1)
    :param q_sqrt: tensor of shape (1, n, n). Lower triangular matrix
    :return: tensor with shape (count, D, 1)
    """
    count = phi.shape[0]
    n = phi.shape[1]
    D = phi.shape[2]

    standard_normal = tfp.distributions.MultivariateNormalDiag(
            loc=tf.zeros(n, dtype=tf.float64),
            scale_diag=tf.ones(n, dtype=tf.float64))
    standard_normal_samples = standard_normal.sample(count)
    # (count, n)

    q_samples = q_sqrt @ tf.expand_dims(standard_normal_samples, axis=-1) + q_mu
    # (count,n,1)

    transposed_phi = tf.linalg.matrix_transpose(phi)
    # (count, D, n)

    transform_mat = tf.cond(n >= D,
        true_fn = lambda : tf.linalg.inv(transposed_phi @ phi) @ transposed_phi,
        false_fn = lambda: transposed_phi @ tf.linalg.inv(phi @ transposed_phi) ) # (count, D, n)

    theta = transform_mat @ q_samples
    # (count, D, 1)

    return theta


def sample_features_weights(X, model, D):
    # Ensure phi @ transposed_phi is invertible
    invertible = False
    fail_count = 0
    while not invertible:
        try:
            phi, W, b = sample_fourier_features(X, model.kernel, D)  # phi has shape (count, n, D)
            theta = sample_theta_variational(phi, model.q_mu, model.q_sqrt)
            invertible = True
        except tf.errors.InvalidArgumentError as err:  # this will be thrown if matrix inversion fails
            print(err)
            print("Resampling phi, W, b, theta")
            fail_count += 1
        if fail_count >= 100:
            print("Retry limit exceeded")
            raise ValueError("Failed")

    return phi, W, b, theta


def sample_maximizers(X, count, n_init, D, model, min_val, max_val, num_steps=3000):
    """
    Samples from the posterior over the global maximizer using the method by Shah & Ghahramani (2015). Approximates
    the RBF kernel with its Fourier dual. Samples random Fourier features, constructs a linear model and computes
    the argmax using gradient-based optimization.

    :param X: input points, tensor with shape (n, d)
    :param count: number of maximizers to sample. Each will be taken from one separate function sample
    :param n_init: Number of initializing points for each function sample. This method will take the argmax of all
    initializing points after optimization, so that each function sample will have one maximizer returned
    :param D: number of Fourier features to use
    :param model: gpflow model that uses the RBF kernel and has been optimized
    :param min_val: float, min value that a maximizer can take
    :param max_val: float, max value that a maximizer can take
    :param num_steps: int that specifies how many optimization steps to take
    :return: tensor of shape (count, d)
    """
    d = X.shape[1]

    X = tf.tile(tf.expand_dims(X, axis=0), [count, 1, 1])  # (count, n, d)

    phi, W, b, theta = sample_features_weights(X, model, D)

    def construct_maximizer_objective(x_star):
        g = tf.reduce_mean(fourier_features(x_star, W, b) @ theta)
        return -g

    # Compute x_star using gradient based methods
    # optimizer = tf.keras.optimizers.Adam()
    optimizer = tf.keras.optimizers.RMSprop(rho=0.0)

    x_star = tf.Variable(tf.random.uniform(shape=(count, n_init, d),
                                           minval=min_val,
                                           maxval=max_val,
                                           dtype=tf.dtypes.float64),
                         constraint=lambda x: tf.clip_by_value(x, min_val, max_val))
    loss = lambda: construct_maximizer_objective(x_star)

    prev_loss = loss().numpy()
    for i in range(num_steps):
        optimizer.minimize(loss, var_list=[x_star])
        current_loss = loss().numpy()
        if i % 500 == 0:
            print('Loss at step %s: %s' % (i, current_loss))
        if abs((current_loss-prev_loss) / prev_loss) < 1e-7:
            print('Loss at step %s: %s' % (i, current_loss))
            break
        prev_loss = current_loss

    test = fourier_features(x_star, W, b) @ theta
    print("test.shape = ", test.numpy().shape)

    fvals = tf.squeeze(fourier_features(x_star, W, b) @ theta, axis=2)
    # (count, n_init)
    max_idxs = tf.transpose(tf.stack([tf.range(count, dtype=tf.int64),
                         tf.math.argmax(fvals, axis=1)]))

    maximizers = tf.gather_nd(x_star, indices=max_idxs)

    return maximizers
