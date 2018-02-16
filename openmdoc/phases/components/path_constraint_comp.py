from __future__ import division, print_function

import numpy as np
from openmdao.api import ExplicitComponent

from openmdoc.phases.grid_data import GridData


class PathConstraintComp(ExplicitComponent):

    def initialize(self):
        self._path_constraints = []
        self._vars = []

        self.metadata.declare('transcription', values=['gauss-lobatto', 'radau-ps'],
                              desc='Transcription technique of the optimal control problem.')

        self.metadata.declare('grid_data', types=GridData,
                              desc='Container object for grid info')

    def setup(self):
        """
        Define the independent variables as output variables.
        """
        grid_data = self.metadata['grid_data']
        transcription = self.metadata['transcription']

        num_nodes = grid_data.num_nodes
        num_disc_nodes = grid_data.subset_num_nodes['disc']
        num_col_nodes = grid_data.subset_num_nodes['col']
        for (name, kwargs) in self._path_constraints:
            disc_input_name = 'disc_values:{0}'.format(name)
            col_input_name = 'col_values:{0}'.format(name)
            output_name = 'path:{0}'.format(name)
            input_kwargs = {k: kwargs[k] for k in ('units', 'desc', 'var_set')}
            output_kwargs = {k: kwargs[k] for k in ('units', 'desc', 'var_set')}
            output_kwargs['shape'] = (num_nodes,) + kwargs['shape']
            constraint_kwargs = {k: kwargs.get(k, None)
                                 for k in ('lower', 'upper', 'equals', 'ref', 'ref0', 'adder',
                                           'scaler', 'indices', 'linear')}
            self.add_input(disc_input_name,
                           shape=(num_disc_nodes,) + kwargs['shape'],
                           **input_kwargs)

            if self.metadata['transcription'] == 'gauss-lobatto':
                self.add_input(col_input_name,
                               shape=(num_col_nodes,) + kwargs['shape'],
                               **input_kwargs)

            self.add_output(output_name, **output_kwargs)

            self._vars.append((disc_input_name, col_input_name, output_name, kwargs['shape']))
            self.add_constraint(output_name, **constraint_kwargs)

        # Setup partials
        for (disc_input_name, col_input_name, output_name, shape) in self._vars:
            disc_shape = (num_disc_nodes,) + shape
            col_shape = (num_col_nodes,) + shape

            var_size = np.prod(shape)
            disc_size = np.prod(disc_shape)
            col_size = np.prod(col_shape)

            disc_row_starts = grid_data.subset_node_indices['disc'] * var_size
            disc_rows = []
            for i in disc_row_starts:
                disc_rows.extend(range(i, i + var_size))
            disc_rows = np.asarray(disc_rows, dtype=int)

            self.declare_partials(
                of=output_name,
                wrt=disc_input_name,
                dependent=True,
                rows=disc_rows,
                cols=np.arange(disc_size),
                val=1.0)

            if transcription == 'gauss-lobatto':

                col_row_starts = grid_data.subset_node_indices['col'] * var_size
                col_rows = []
                for i in col_row_starts:
                    col_rows.extend(range(i, i + var_size))
                col_rows = np.asarray(col_rows, dtype=int)

                self.declare_partials(
                    of=output_name,
                    wrt=col_input_name,
                    dependent=True,
                    rows=col_rows,
                    cols=np.arange(col_size),
                    val=1.0)

    def _compute_radau(self, inputs, outputs):
        for (disc_input_name, col_input_name, output_name, _) in self._vars:
            outputs[output_name] = inputs[disc_input_name]

    def _compute_gauss_lobatto(self, inputs, outputs):
        disc_indices = self.metadata['grid_data'].subset_node_indices['disc']
        col_indices = self.metadata['grid_data'].subset_node_indices['col']
        for (disc_input_name, col_input_name, output_name, _) in self._vars:
            outputs[output_name][disc_indices] = inputs[disc_input_name]
            outputs[output_name][col_indices] = inputs[col_input_name]

    def compute(self, inputs, outputs):
        transcription = self.metadata['transcription']
        if transcription == 'gauss-lobatto':
            self._compute_gauss_lobatto(inputs, outputs)
        elif transcription == 'radau-ps':
            self._compute_radau(inputs, outputs)
        else:
            raise ValueError('invalid transcription: {0}'.format(transcription))

    def _add_path_constraint(self, name, shape=(1,), units=None, res_units=None, desc='',
                             lower=None, upper=None, equals=None, scaler=None, adder=None,
                             ref=None, ref0=None, linear=False, res_ref=1.0, var_set=0,
                             distributed=False):
        """
        Add a final constraint to this component

        Parameters
        ----------
        name : str
            name of the variable in this component's namespace.
        val : float or list or tuple or ndarray
            The initial value of the variable being added in user-defined units. Default is 1.0.
        shape : int or tuple or list or None
            Shape of this variable, only required if val is not an array.
            Default is None.
        units : str or None
            Units in which the output variables will be provided to the component during execution.
            Default is None, which means it has no units.
        res_units : str or None
            Units in which the residuals of this output will be given to the user when requested.
            Default is None, which means it has no units.
        desc : str
            description of the variable
        lower : float or list or tuple or ndarray or None
            lower bound(s) in user-defined units. It can be (1) a float, (2) an array_like
            consistent with the shape arg (if given), or (3) an array_like matching the shape of
            val, if val is array_like. A value of None means this output has no lower bound.
            Default is None.
        upper : float or list or tuple or ndarray or None
            upper bound(s) in user-defined units. It can be (1) a float, (2) an array_like
            consistent with the shape arg (if given), or (3) an array_like matching the shape of
            val, if val is array_like. A value of None means this output has no upper bound.
            Default is None.
        ref : float
            Scaling parameter. The value in the user-defined units of this output variable when
            the scaled value is 1. Default is 1.
        ref0 : float
            Scaling parameter. The value in the user-defined units of this output variable when
            the scaled value is 0. Default is 0.
        linear : bool
            True if the *total* derivative of the constrained variable is linear, otherwise False.
        res_ref : float
            Scaling parameter. The value in the user-defined res_units of this output's residual
            when the scaled value is 1. Default is 1.
        var_set : hashable object
            For advanced users only. ID or color for this variable, relevant for reconfigurability.
            Default is 0.
        distributed : bool
            If True, this variable is distributed across multiple processes.
        """
        kwargs = {'shape': shape, 'units': units, 'res_units': res_units, 'desc': desc,
                  'lower': lower, 'upper': upper, 'equals': equals, 'scaler': scaler,
                  'adder': adder, 'ref': ref, 'ref0': ref0, 'linear': linear,
                  'res_ref': res_ref, 'var_set': var_set, 'distributed': distributed}
        self._path_constraints.append((name, kwargs))