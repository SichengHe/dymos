import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.style.use('ggplot')

from openmdao.utils.testing_utils import use_tempdirs, require_pyoptsparse


@use_tempdirs
class TestMinTimeClimbForDocs(unittest.TestCase):

    @require_pyoptsparse(optimizer='IPOPT')
    def test_min_time_climb_partial_coloring(self):
        import openmdao.api as om
        from openmdao.utils.assert_utils import assert_near_equal

        import dymos as dm
        from dymos.examples.min_time_climb.doc.min_time_climb_ode_partial_coloring import MinTimeClimbODE

        #
        # Instantiate the problem and configure the optimization driver
        #
        p = om.Problem(model=om.Group())

        p.driver = om.pyOptSparseDriver()
        p.driver.options['optimizer'] = 'IPOPT'
        p.driver.opt_settings['print_level'] = 0
        p.driver.opt_settings['tol'] = 1.0E-5
        p.driver.declare_coloring(tol=1.0E-12)

        #
        # Instantiate the trajectory and phase
        #
        traj = dm.Trajectory()

        phase = dm.Phase(ode_class=MinTimeClimbODE,
                         ode_init_kwargs={'fd': True, 'partial_coloring': True},
                         transcription=dm.GaussLobatto(num_segments=30))

        traj.add_phase('phase0', phase)

        p.model.add_subsystem('traj', traj)

        #
        # Set the options on the optimization variables
        #
        phase.set_time_options(fix_initial=True, duration_bounds=(50, 400),
                               duration_ref=100.0)

        phase.add_state('r', fix_initial=True, lower=0, upper=1.0E6,
                        ref=1.0E3, defect_ref=1.0E3, units='m',
                        rate_source='flight_dynamics.r_dot')

        phase.add_state('h', fix_initial=True, lower=0, upper=20000.0,
                        ref=1.0E2, defect_ref=1.0E2, units='m',
                        rate_source='flight_dynamics.h_dot')

        phase.add_state('v', fix_initial=True, lower=10.0,
                        ref=1.0E2, defect_ref=1.0E2, units='m/s',
                        rate_source='flight_dynamics.v_dot')

        phase.add_state('gam', fix_initial=True, lower=-1.5, upper=1.5,
                        ref=1.0, defect_ref=1.0, units='rad',
                        rate_source='flight_dynamics.gam_dot')

        phase.add_state('m', fix_initial=True, lower=10.0, upper=1.0E5,
                        ref=1.0E3, defect_ref=1.0E3, units='kg',
                        rate_source='prop.m_dot')

        phase.add_control('alpha', units='deg', lower=-8.0, upper=8.0, scaler=1.0,
                          rate_continuity=True, rate_continuity_scaler=100.0,
                          rate2_continuity=False, targets=['alpha'])

        phase.add_parameter('S', val=49.2386, units='m**2', opt=False, targets=['S'])
        phase.add_parameter('Isp', val=1600.0, units='s', opt=False, targets=['Isp'])
        phase.add_parameter('throttle', val=1.0, opt=False, targets=['throttle'])

        #
        # Setup the boundary and path constraints
        #
        phase.add_boundary_constraint('h', loc='final', equals=20000, scaler=1.0E-3)
        phase.add_boundary_constraint('aero.mach', loc='final', equals=1.0)
        phase.add_boundary_constraint('gam', loc='final', equals=0.0)

        phase.add_path_constraint(name='h', lower=100.0, upper=20000, ref=20000)
        phase.add_path_constraint(name='aero.mach', lower=0.1, upper=1.8)

        # Minimize time at the end of the phase
        phase.add_objective('time', loc='final', ref=100.0)

        p.model.linear_solver = om.DirectSolver()

        #
        # Setup the problem and set the initial guess
        #
        p.setup()

        p['traj.phase0.t_initial'] = 0.0
        p['traj.phase0.t_duration'] = 500

        p['traj.phase0.states:r'] = phase.interp('r', [0.0, 50000.0])
        p['traj.phase0.states:h'] = phase.interp('h', [100.0, 20000.0])
        p['traj.phase0.states:v'] = phase.interp('v', [135.964, 283.159])
        p['traj.phase0.states:gam'] = phase.interp('gam', [0.0, 0.0])
        p['traj.phase0.states:m'] = phase.interp('m', [19030.468, 10000.])
        p['traj.phase0.controls:alpha'] = phase.interp('alpha', [0.0, 0.0])

        #
        # Solve for the optimal trajectory
        #
        dm.run_problem(p)

        #
        # Test the results
        #
        assert_near_equal(p.get_val('traj.phase0.t_duration'), 321.0, tolerance=1.0E-1)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
