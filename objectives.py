import numpy as np


def forrester(x):
    """
    1-dimensional test function by Forrester et al. (2008)
    Defined as f(x) = (6x-2)^2 * sin(12x-4)
    :param x: tensor of shape (..., 1), x1 in [0, 1]
    :return: tensor of shape (..., )
    """
    x0 = x[..., 0]
    return (6 * x0 - 2) * (6 * x0 - 2) * np.sin(12 * x0 - 4)


def six_hump_camel(x):
    """
    2-D test function by Molga & Smutnicki (2005), restricted to [-1.5, 1.5] on both dimensions. 2 global minima.
     Has global minimum f(x) = -1.0316, at x = [0.0898, -0.7126] and x = [-0.0898, 0.7126]
    :param x: tensor of shape (..., 2), x1 in [-2, 2], x2 in [-2, 2]
    :return: tensor of shape (..., )
    """
    x1 = x[..., 0]
    x2 = x[..., 1]
    return (4. - 2.1 * (x1 ** 2) + (1. / 3.) * (x1 ** 4)) * (x1 ** 2) + (x1 * x2) + (-4. + 4 * (x2 ** 2)) * (x2 ** 2)


def hartmann3d(x):
    """
    3-D test function from Unconstrained Global Optimization Test Problems, at
    http://www-optima.amp.i.kyoto-u.ac.jp/member/student/hedar/Hedar_files/TestGO.htm
    Has 4 local minima, one of which is global. Has global minimum f(x) = -3.86278, at x = [0.114614, 0.555649,
    0.852547]
    :param x: tensor of shape (..., 3), x in [0, 1] for all dimensions
    :return: tensor of shape (..., )
    """
    alpha = np.array([1., 1.2, 3.0, 3.2])
    A = np.array([[3.0, 10, 30],
                  [0.1, 10, 35],
                  [3.0, 10, 30],
                  [0.1, 10, 35]])
    P = 0.0001 * np.array([[3689, 1170, 2673],
                           [4699, 4387, 7470],
                           [1091, 8732, 5547],
                           [381, 5743, 8828]])

    x_repeat = np.repeat(np.expand_dims(x, axis=-2), 4, axis=-2)
    return -np.sum(alpha * np.exp(-np.sum(A * ((x_repeat - P) ** 2), axis=-1)), axis=-1)


def cifar(x, embedding_to_class):
    """
    2-D test function over 2-D embeddings of CIFAR-10 images. We define an arbitrary preference over classes as such:
    Airplane (0) > Automobile (1) > Ship (8) > Truck (9) > Bird (2) > Cat (3) > Deer (4) > Dog (5) > Frog (6) > Horse
    (7)

    :param x: tensor of shape (..., 2). CIFAR-10 embeddings
    :param embedding_to_class: dict
    :return: tensor of shape (..., 1). last dim is int from 0-9 representing class
    """
    class_to_fval = {0: -5.,
                     1: -4.,
                     8: -3.,
                     9: -2.,
                     2: -1.,
                     3: 0.,
                     4: 1.,
                     5: 2.,
                     6: 3.,
                     7: 4.}  # smaller is more preferred

    shape = x.shape[:-1]
    raveled = np.reshape(x, [-1, 2])
    raveled_shape = raveled.shape[:-1]
    raveled_fvals = np.zeros((raveled_shape[0], 1), dtype=np.float64)

    for i in range(raveled_shape[0]):
        raveled_fvals[i] = class_to_fval[embedding_to_class[raveled[i].data.tobytes()]]

    return np.reshape(raveled_fvals, shape + (1,))


def sushi(x, feat_to_fval_dict):
    """
    6-D test function over the Sushi dataset with the minor group feature removed (overlaps with major group).
    :param x: tensor of shape (..., 6). Sushi datum
    :param feat_to_fval_dict: dictionary from sushi features to fval
    :return: tensor of shape (..., ). Returns the fvals of each sushi datum in the array
    """

    input_dims = x.shape[-1]
    shape = x.shape[:-1]  # shape except last dim
    raveled = np.reshape(x, [-1, input_dims])
    raveled_shape = raveled.shape[:-1]
    raveled_fvals = np.zeros((raveled_shape[0]), dtype=np.float64)

    for i in range(raveled_shape[0]):
        raveled_fvals[i] = -feat_to_fval_dict[raveled[i].data.tobytes()]  # here smaller is more preferred

    return np.reshape(raveled_fvals, shape)


def objective_get_f_neg(x, objective):
    """
    Get objective function values of inputs. Note that this returns the negative of the above objective functions,
    as observation_model.gen_observation_from_f takes it that more positive functions values are preferred, while we
    are interested in finding the minima of the above functions.
    :param x: tensor of shape (..., num_choices, input_dims)
    :param objective: function that takes tensor of shape (..., input_dims) and outputs tensor of shape (..., ) with
    the objective function values
    :return: tensor of shape (..., 1)
    """
    return -np.expand_dims(objective(x), axis=-1)


def objective_get_y(x, objective):
    """
    Returns tensor with argmins of input array (input point with the lowest objective function value among choices)
    :param x: tensor of shape (..., num_choices, input_dims)
    :param objective: function that takes tensor of shape (..., input_dims) and outputs tensor of shape (..., ) with
    the objective function values
    :return: tensor of shape (..., input_dims)
    """
    evals = objective(x)  # (..., num_choices)
    indices = np.argmin(evals, axis=1)[:, np.newaxis, np.newaxis]  # (..., 1, 1)
    return np.squeeze(np.take_along_axis(x, indices, axis=-2), axis=-2)
