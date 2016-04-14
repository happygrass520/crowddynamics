import numba
import numpy as np


@numba.jit(nopython=True, nogil=True)
def f_soc_ij(xi, xj, vi, vj, ri, rj, tau_0, sight, f_max):
    r"""
    About
    -----
    Social interaction force between two agents `i` and `j`. [1]

    Params
    ------
    :param xi: Position (center of mass) of agent i.
    :param xj: Position (center of mass) of agent j.
    :param vi: Velocity of agent i.
    :param vj: Velocity of agent j.
    :param ri: Radius of agent i.
    :param rj: Radius of agent j.
    :param tau_0: Max interaction range 2 - 4, aka interaction time horizon
    :param sight: Max distance between agents for interaction to occur
    :param f_max: Maximum magnitude of force. Forces greater than this are scaled to force max.
    :return: Vector of length 2 containing `x` and `y` components of force
             on agent i.

    References
    ----------
    [1] http://motion.cs.umn.edu/PowerLaw/
    """
    # Init output values.
    force = np.zeros(2)

    # Variables
    x_ij = xi - xj  # position
    v_ij = vi - vj  # velocity
    r_ij = ri + rj  # radius

    x_dot = np.dot(x_ij, x_ij)
    dist = np.sqrt(x_dot)
    # No force if another agent is not in range of sight
    if dist > sight:
        return force

    # TODO: Update overlapping to f_c_ij
    # If two agents are overlapping reduce r
    if r_ij > dist:
        r_ij = 0.50 * dist

    a = np.dot(v_ij, v_ij)
    b = - np.dot(x_ij, v_ij)
    c = x_dot - r_ij ** 2
    d = b ** 2 - a * c

    if (d < 0) or (- 0.001 < a < 0.001):
        return force

    d = np.sqrt(d)
    tau = (b - d) / a  # Time-to-collision

    k = 1.5  # Constant for setting units for interaction force. Scale with mass
    m = 2.0  # Exponent in power law
    maxt = 999.0

    if tau < 0 or tau > maxt:
        return force

    # Force is returned negative as repulsive force
    force -= k / (a * tau ** m) * np.exp(-tau / tau_0) * \
             (m / tau + 1 / tau_0) * (v_ij - (v_ij * b + x_ij * a) / d)

    mag = np.sqrt(np.dot(force, force))
    if mag > f_max:
        # Scales magnitude of force to force max
        force *= f_max / mag

    return force


@numba.jit(nopython=True, nogil=True)
def f_c_ij(h_ij, n_ij, v_ij, t_ij, mu, kappa):
    force = h_ij * (mu * n_ij - kappa * np.dot(v_ij, t_ij) * t_ij)
    return force


@numba.jit(nopython=True, nogil=True)
def f_soc_ij_tot(i, x, v, r, tau_0, sight, force_max):
    # TODO: Update to f_ij
    force = np.zeros(2)
    for j in range(len(x)):
        if i == j:
            continue
        force += f_soc_ij(x[i], x[j], v[i], v[j], r[i], r[j],
                          tau_0, sight, force_max)
    return force


def f_ij(i, x, v, r, tau_0, sight, f_max, mu, kappa):
    force = np.zeros(2)
    rot270 = np.array([[0, 1], [-1, 0]])
    for j in range(len(x)):
        if i == j:
            continue
        x_ij = x[i] - x[j]
        v_ij = v[i] - v[j]
        x_dot = np.dot(x_ij, x_ij)
        d_ij = np.sqrt(x_dot)
        r_ij = r[i] + r[j]
        h_ij = d_ij - r_ij
        n_ij = x_ij / d_ij
        t_ij = np.dot(rot270, n_ij)

        force += f_soc_ij(x[i], x[j], v[i], v[j], r[i], r[j],
                          tau_0, sight, f_max)

        force += f_c_ij(h_ij, n_ij, v_ij, t_ij, mu, kappa)
    return force


@numba.jit(nopython=True, nogil=True)
def f_soc_iw(r_i, d_iw, n_iw, a_i, b_i):
    """
    Params
    ------
    :param a_i: Coefficient
    :param b_i: Coefficient
    :param r_i: Radius of the agent
    :param d_iw: Distance to the wall
    :param n_iw: Unit vector that is perpendicular to the agent and the wall
    :return:
    """
    force = a_i * np.exp((r_i - d_iw) / b_i) * n_iw
    return force


@numba.jit(nopython=True, nogil=True)
def f_c_iw(h_iw, n_iw, v_i, t_iw, mu, kappa):
    force = h_iw * (mu * n_iw - kappa * np.dot(v_i, t_iw) * t_iw)
    return force


@numba.jit(nopython=True, nogil=True)
def f_iw_linear(x_i, v_i, r_i, p_0, p_1, t_w, n_w, l_w, sight, a, b, mu, kappa):
    force = np.zeros(2)

    q_0 = x_i - p_0
    q_1 = x_i - p_1

    q = np.zeros((2, 2))
    q[:, 0] = q_0
    q[:, 1] = q_1
    l_t = np.dot(t_w, q)
    l_t = l_t[1] - l_t[1]

    if l_t > l_w:
        d_iw = np.sqrt(np.dot(q_0, q_0))
        n_iw = q_0
    elif l_t < l_w:
        d_iw = np.sqrt(np.dot(q_1, q_1))
        n_iw = q_1
    else:
        l_n = np.dot(n_w, q_0)
        d_iw = np.abs(l_n)
        n_iw = np.sign(l_n) * n_w

    if d_iw <= sight:
        force += f_soc_iw(r_i, d_iw, n_iw, a, b)

    h_iw = r_i - d_iw
    if h_iw > 0:
        rot270 = np.array([[0, 1], [-1, 0]])  # -90 degree rotation
        t_iw = np.dot(rot270, n_iw)
        force += f_c_iw(h_iw, n_iw, v_i, t_iw, mu, kappa)

    return force


def f_iw_tot(i, x, v, r, w, f_max, sight, mu, kappa, a, b):
    force = np.zeros(2)

    for i in range(len(w)):
        # TODO: wall object unpacking
        p_0, p_1, t_w, n_w, l_w = w[i]
        force += f_iw_linear(x[i], v[i], r[i], p_0, p_1, t_w, n_w, l_w,
                             sight, a, b, mu, kappa)

    return force


@numba.jit(nopython=True, nogil=True)
def f_random_fluctuation():
    """

    :return: Uniformly distributed random force.
    """
    force = np.zeros(2)
    for i in range(len(force)):
        # for loop so compilation can be done with numba
        force[i] = np.random.uniform(-1, 1)
    return force


def e_i_0(e_i, p_i):
    """
    Update goal direction.
    """
    pass


@numba.jit(nopython=True, nogil=True)
def f_adjust_i(v_0_i, v_i, mass_i, tau_i):
    """
    Params
    ------
    :param v_0_i: Goal velocity of an agent
    :param v_i: Current velocity
    :param mass_i: Mass of an agent
    :param tau_i: Characteristic time where agent adapts its movement from current velocity to goal velocity
    :return: Vector of length 2 containing `x` and `y` components of force on agent i.
    """
    # TODO: v_0 = v_0 * e_i
    force = (v_0_i - v_i) * mass_i / tau_i
    return force


@numba.jit(nopython=True, nogil=True)
def f_tot_i(i, v_0, v, x, r, mass,
            tau, tau_0, sight, f_max, mu, kappa, a, b):
    """
    Total force on individual agent i.

    :return: Vector of length 2 containing `x` and `y` components of force
             on agent i.
    """
    force = np.zeros(2)
    force += f_adjust_i(v_0, v[i], mass, tau)
    force += f_random_fluctuation()

    # Agent-Agent
    force += f_soc_ij_tot(i, x, v, r, tau_0, sight, f_max)

    # Agent-Wall

    return force


@numba.jit(nopython=True, nogil=True)
def acceleration(goal_velocity, velocity, position, radius, mass,
                 tau_adj, tau_0, sight, f_max, mu, kappa, a, b):
    """
    About
    -----
    Total forces on all agents in the system. Uses `Helbing's` social force model
    [1] and with power law [2].

    Params
    ------
    :return: Array of forces.

    References
    ----------
    [1] http://www.nature.com/nature/journal/v407/n6803/full/407487a0.html \n
    [2] http://motion.cs.umn.edu/PowerLaw/
    """
    # TODO: AOT complilation
    # TODO: Adaptive Euler Method
    acc = np.zeros_like(velocity)
    for i in range(len(position)):
        f = f_tot_i(i, goal_velocity[i], velocity, position, radius, mass[i],
                    tau_adj, tau_0, sight, f_max, mu, kappa, a, b)
        acc[i] = f / mass[i]
    return acc
