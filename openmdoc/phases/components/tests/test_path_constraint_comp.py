from __future__ import print_function, division, absolute_import

import unittest

import numpy as np
from numpy.testing import assert_almost_equal
from openmdao.api import Problem, Group, IndepVarComp
from openmdao.utils.assert_utils import assert_check_partials

from openmdoc.phases.components import PathConstraintComp
from openmdoc.phases.grid_data import GridData
from openmdoc.phases.options import ControlOptionsDictionary


class TestPathConstraintCompGL(unittest.TestCase):

    def setUp(self):

        transcription = 'gauss-lobatto'

        self.gd = gd = GridData(num_segments=2,
                                transcription_order=3,
                                segment_ends=[0.0, 3.0, 10.0],
                                transcription=transcription)

        ndn = gd.subset_num_nodes['disc']
        ncn = gd.subset_num_nodes['col']

        self.p = Problem(model=Group())

        controls = {'a': ControlOptionsDictionary(),
                    'b': ControlOptionsDictionary(),
                    'c': ControlOptionsDictionary(),
                    'd': ControlOptionsDictionary()}

        controls['a'].update({'units': 'm', 'shape': (1,), 'dynamic': True, 'opt': False})
        controls['b'].update({'units': 's', 'shape': (3,), 'dynamic': True, 'opt': False})
        controls['c'].update({'units': 'kg', 'shape': (3, 3), 'dynamic': True, 'opt': False})

        ivc = IndepVarComp()
        self.p.model.add_subsystem('ivc', ivc, promotes_outputs=['*'])

        ivc.add_output('a_disc', val=np.zeros((ndn, 1)), units='m')
        ivc.add_output('a_col', val=np.zeros((ncn, 1)), units='m')
        ivc.add_output('b_disc', val=np.zeros((ndn, 3)), units='s')
        ivc.add_output('b_col', val=np.zeros((ncn, 3)), units='s')
        ivc.add_output('c_disc', val=np.zeros((ndn, 3, 3)), units='kg')
        ivc.add_output('c_col', val=np.zeros((ncn, 3, 3)), units='kg')

        path_comp = PathConstraintComp(transcription=transcription, grid_data=gd)

        self.p.model.add_subsystem('path_constraints', subsys=path_comp)

        path_comp._add_path_constraint('a', shape=(1,), lower=0, upper=10, units='m')
        path_comp._add_path_constraint('b', shape=(3,), lower=0, upper=10, units='s')
        path_comp._add_path_constraint('c', shape=(3, 3), lower=0, upper=10, units='kg')

        self.p.model.connect('a_disc', 'path_constraints.disc_values:a')
        self.p.model.connect('a_col', 'path_constraints.col_values:a')

        self.p.model.connect('b_disc', 'path_constraints.disc_values:b')
        self.p.model.connect('b_col', 'path_constraints.col_values:b')

        self.p.model.connect('c_disc', 'path_constraints.disc_values:c')
        self.p.model.connect('c_col', 'path_constraints.col_values:c')

        self.p.setup(mode='fwd')

        self.p['a_disc'] = np.random.rand(*self.p['a_disc'].shape)
        self.p['a_col'] = np.random.rand(*self.p['a_col'].shape)

        self.p['b_disc'] = np.random.rand(*self.p['b_disc'].shape)
        self.p['b_col'] = np.random.rand(*self.p['b_col'].shape)

        self.p['c_disc'] = np.random.rand(*self.p['c_disc'].shape)
        self.p['c_col'] = np.random.rand(*self.p['c_col'].shape)

        self.p.run_model()

    def test_results(self):
        p = self.p
        gd = self.gd
        assert_almost_equal(p['a_disc'],
                            p['path_constraints.path:a'][gd.subset_node_indices['disc'], ...])

        assert_almost_equal(p['a_col'],
                            p['path_constraints.path:a'][gd.subset_node_indices['col'], ...])

        assert_almost_equal(p['b_disc'],
                            p['path_constraints.path:b'][gd.subset_node_indices['disc'], ...])

        assert_almost_equal(p['b_col'],
                            p['path_constraints.path:b'][gd.subset_node_indices['col'], ...])

        assert_almost_equal(p['c_disc'],
                            p['path_constraints.path:c'][gd.subset_node_indices['disc'], ...])

        assert_almost_equal(p['c_col'],
                            p['path_constraints.path:c'][gd.subset_node_indices['col'], ...])

    def test_partials(self):
        np.set_printoptions(linewidth=1024, edgeitems=1000)
        cpd = self.p.check_partials(suppress_output=True)
        assert_check_partials(cpd)


class TestPathConstraintCompRadau(unittest.TestCase):

    def setUp(self):

        transcription = 'radau-ps'

        self.gd = gd = GridData(num_segments=2,
                                transcription_order=3,
                                segment_ends=[0.0, 3.0, 10.0],
                                transcription=transcription)

        ndn = gd.subset_num_nodes['disc']

        self.p = Problem(model=Group())

        controls = {'a': ControlOptionsDictionary(),
                    'b': ControlOptionsDictionary(),
                    'c': ControlOptionsDictionary(),
                    'd': ControlOptionsDictionary()}

        controls['a'].update({'units': 'm', 'shape': (1,), 'dynamic': True, 'opt': False})
        controls['b'].update({'units': 's', 'shape': (3,), 'dynamic': True, 'opt': False})
        controls['c'].update({'units': 'kg', 'shape': (3, 3), 'dynamic': True, 'opt': False})

        ivc = IndepVarComp()
        self.p.model.add_subsystem('ivc', ivc, promotes_outputs=['*'])

        ivc.add_output('a_disc', val=np.zeros((ndn, 1)), units='m')
        ivc.add_output('b_disc', val=np.zeros((ndn, 3)), units='s')
        ivc.add_output('c_disc', val=np.zeros((ndn, 3, 3)), units='kg')

        path_comp = PathConstraintComp(transcription=transcription, grid_data=gd)

        self.p.model.add_subsystem('path_constraints', subsys=path_comp)

        path_comp._add_path_constraint('a', shape=(1,), lower=0, upper=10, units='m')
        path_comp._add_path_constraint('b', shape=(3,), lower=0, upper=10, units='s')
        path_comp._add_path_constraint('c', shape=(3, 3), lower=0, upper=10, units='kg')

        self.p.model.connect('a_disc', 'path_constraints.disc_values:a')
        self.p.model.connect('b_disc', 'path_constraints.disc_values:b')
        self.p.model.connect('c_disc', 'path_constraints.disc_values:c')

        self.p.setup(mode='fwd')

        self.p.run_model()

    def test_results(self):
        p = self.p
        gd = self.gd
        assert_almost_equal(p['a_disc'],
                            p['path_constraints.path:a'][gd.subset_node_indices['disc'], ...])

        assert_almost_equal(p['b_disc'],
                            p['path_constraints.path:b'][gd.subset_node_indices['disc'], ...])

        assert_almost_equal(p['c_disc'],
                            p['path_constraints.path:c'][gd.subset_node_indices['disc'], ...])

    def test_partials(self):
        np.set_printoptions(linewidth=1024, edgeitems=1000)
        cpd = self.p.check_partials(suppress_output=True)
        assert_check_partials(cpd)


if __name__ == '__main__':
    unittest.main()