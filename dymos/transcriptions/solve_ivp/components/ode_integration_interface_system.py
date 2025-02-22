import numpy as np
from .odeint_control_interpolation_comp import ODEIntControlInterpolationComp
from .state_rate_collector_comp import StateRateCollectorComp
from ....phase.options import TimeOptionsDictionary
from ....utils.introspection import get_promoted_vars
import openmdao.api as om


class ODEIntegrationInterfaceSystem(om.Group):
    """
    Class definition for ODEIntegrationInterfaceSystem.

    Parameters
    ----------
    **kwargs : dict
        Dictionary of optional arguments.
    """
    def initialize(self):
        """
        Declare group options.
        """
        self.options.declare('time_options', types=TimeOptionsDictionary,
                             desc='Time options for the phase')

        self.options.declare('state_options', types=dict,
                             desc='Dictionary of state names/options for the segments parent Phase')

        self.options.declare('control_options', default=None, types=dict, allow_none=True,
                             desc='Dictionary of control names/options for the segments parent Phase.')

        self.options.declare('polynomial_control_options', default=None, types=dict, allow_none=True,
                             desc='Dictionary of polynomial control names/options for the segments '
                                  'parent Phase.')

        self.options.declare('parameter_options', default=None, types=dict, allow_none=True,
                             desc='Dictionary of parameter names/options for the segments '
                                  'parent Phase.')

        self.options.declare('ode_class',
                             desc='System defining the ODE')

        self.options.declare('ode_init_kwargs', types=dict, default={},
                             desc='Keyword arguments provided when initializing the ODE System')

    def setup(self):
        """
        Create the group hierarchy.
        """
        ivc = om.IndepVarComp()
        time_options = self.options['time_options']
        time_units = time_options['units']
        ivc.add_output('time', val=0.0, units=time_units)
        ivc.add_output('time_phase', val=-88.0, units=time_units)
        ivc.add_output('t_initial', val=-99.0, units=time_units)
        ivc.add_output('t_duration', val=-111.0, units=time_units)

        self.add_subsystem('ivc', ivc, promotes_outputs=['*'])

        self.connect('time', [f'ode.{tgt}' for tgt in time_options['targets']])

        self.connect('time_phase', [f'ode.{tgt}' for tgt in time_options['time_phase_targets']])

        self.connect('t_initial', [f'ode.{tgt}' for tgt in time_options['t_initial_targets']])

        self.connect('t_duration', [f'ode.{tgt}' for tgt in time_options['t_duration_targets']])

        if self.options['control_options'] or self.options['polynomial_control_options']:
            self._interp_comp = \
                ODEIntControlInterpolationComp(time_units=time_units,
                                               control_options=self.options['control_options'],
                                               polynomial_control_options=self.options['polynomial_control_options'])

            self.add_subsystem('indep_controls', self._interp_comp, promotes_outputs=['*'])
            self.connect('time', ['indep_controls.time'])

        # The ODE System
        if self.options['ode_class'] is not None:
            self.add_subsystem('ode', subsys=self.options['ode_class'](num_nodes=1,
                                                                       **self.options['ode_init_kwargs']))

        # The state rate collector comp
        self.add_subsystem('state_rate_collector',
                           StateRateCollectorComp(state_options=self.options['state_options'],
                                                  time_units=time_options['units']))

    def configure(self):
        """
        Issue connections after introspection.
        """
        ivc = self._get_subsystem('ivc')
        ode = self._get_subsystem('ode')
        ode_inputs = get_promoted_vars(ode, 'input')

        # Configure states
        for name, options in self.options['state_options'].items():
            size = np.prod(options['shape'])
            ivc.add_output(f'states:{name}',
                           shape=(1, size),
                           units=options['units'])

            rate_src = self._get_rate_source_path(name)

            self.connect(rate_src, f'state_rate_collector.state_rates_in:{name}_rate')

            if options['targets']:
                for tgt in options['targets']:
                    tgt_shape = ode_inputs[tgt]['shape']
                    if len(tgt_shape) == 1 and tgt_shape[0] == 1:
                        src_idxs = np.arange(size, dtype=int).reshape(tgt_shape)
                    else:
                        src_idxs = np.arange(size, dtype=int).reshape((1,) + tgt_shape)
                    self.connect(f'states:{name}', f'ode.{tgt}',
                                 src_indices=(src_idxs,), flat_src_indices=True)

        # Configure controls
        if self.options['control_options']:
            for name, options in self.options['control_options'].items():
                if options['targets']:
                    self.connect(f'controls:{name}',
                                 [f'ode.{tgt}' for tgt in options['targets']])
                if options['rate_targets']:
                    self.connect(f'control_rates:{name}_rate',
                                 [f'ode.{tgt}' for tgt in options['rate_targets']])
                if options['rate2_targets']:
                    self.connect(f'control_rates:{name}_rate2',
                                 [f'ode.{tgt}' for tgt in options['rate2_targets']])

        # Polynomial controls
        if self.options['polynomial_control_options']:
            for name, options in self.options['polynomial_control_options'].items():
                if options['targets']:
                    self.connect(f'polynomial_controls:{name}',
                                 [f'ode.{tgt}' for tgt in options['targets']])
                if options['rate_targets']:
                    self.connect(f'polynomial_control_rates:{name}_rate',
                                 [f'ode.{tgt}' for tgt in options['rate_targets']])
                if options['rate2_targets']:
                    self.connect(f'polynomial_control_rates:{name}_rate2',
                                 [f'ode.{tgt}' for tgt in options['rate2_targets']])

        # Parameters
        if self.options['parameter_options']:
            for name, options in self.options['parameter_options'].items():
                ivc.add_output(f'parameters:{name}', shape=options['shape'], units=options['units'])
                if options['targets']:
                    self.connect(f'parameters:{name}',
                                 [f'ode.{tgt}' for tgt in options['targets']])

    def _get_rate_source_path(self, state_var):
        var = self.options['state_options'][state_var]['rate_source']

        rate_path = f'ode.{var}'

        if var == 'time':
            rate_path = 'time'
        elif var == 'time_phase':
            rate_path = 'time_phase'
        elif self.options['state_options'] is not None and var in self.options['state_options']:
            rate_path = f'states:{var}'
        elif self.options['control_options'] is not None and var in self.options['control_options']:
            rate_path = f'controls:{var}'
        elif self.options['polynomial_control_options'] is not None and var in self.options['polynomial_control_options']:
            rate_path = f'polynomial_controls:{var}'
        elif self.options['parameter_options'] is not None and var in self.options['parameter_options']:
            rate_path = f'parameters:{var}'
        elif var.endswith('_rate') and self.options['control_options'] is not None and \
                var[:-5] in self.options['control_options']:
            rate_path = f'control_rates:{var}'
        elif var.endswith('_rate2') and self.options['control_options'] is not None and \
                var[:-6] in self.options['control_options']:
            rate_path = f'control_rates:{var}'
        elif var.endswith('_rate') and self.options['polynomial_control_options'] is not None and \
                var[:-5] in self.options['polynomial_control_options']:
            rate_path = f'polynomial_control_rates:{var}'
        elif var.endswith('_rate2') and self.options['polynomial_control_options'] is not None and \
                var[:-6] in self.options['polynomial_control_options']:
            rate_path = f'polynomial_control_rates:{var}'

        return rate_path

    def set_interpolant(self, name, interp):
        """
        Set the control and/or polynomial control interpolants in the underlying system.

        Parameters
        ----------
        name : str
            The name of the control or polynomial control whose interpolant is being set.
        interp : LagrangeBarycentricInterpolant
            The LagrangeBarycentricInterpolant for the given control or polynomial control.
        """
        if name in self.options['control_options']:
            self._interp_comp.options['control_interpolants'][name] = interp
        elif name in self.options['polynomial_control_options']:
            self._interp_comp.options['polynomial_control_interpolants'][name] = interp
        else:
            raise KeyError(f'Unable to set control interpolant of unknown control: {name}')

    def setup_interpolant(self, name, x0, xf, f_j):
        """
        Setup the values to be interpolated in an existing interpolant.

        Parameters
        ----------
        name : str
            The name of the control or polynomial control.
        x0 : float
            The initial time (or independent variable) of the segment (for controls) or phase (for polynomial controls).
        xf : float
            The final time (or independent variable) of the segment (for controls) or phase (for polynomial controls).
        f_j : float
            The value of the control at the nodes in the segment or phase.
        """
        if name in self.options['control_options']:
            self._interp_comp.options['control_interpolants'][name].setup(x0, xf, f_j)
        elif name in self.options['polynomial_control_options']:
            self._interp_comp.options['polynomial_control_interpolants'][name].setup(x0, xf, f_j)
        else:
            raise KeyError(f'Unable to setup control interpolant of unknown control: {name}')
