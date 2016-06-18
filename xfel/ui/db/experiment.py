from __future__ import division
from xfel.ui.db import db_proxy
from scitbx.array_family import flex

class Frame(db_proxy):
  def __init__(self, app, frame_id = None, **kwargs):
    db_proxy.__init__(self, app, "%s_frame" % app.params.experiment_tag, id = frame_id, **kwargs)
    self.frame_id = self.id

class Experiment(db_proxy):
  def __init__(self, app, experiment_id = None, experiment = None, **kwargs):
    assert [experiment_id, experiment].count(None) == 1
    if experiment is not None:
      self.imageset = Imageset(app)
      self.beam = Beam(app, beam = experiment.beam)
      self.detector = Detector(app, detector = experiment.detector)
      self.crystal = Crystal(app, crystal = experiment.crystal)

      kwargs['imageset_id'] = self.imageset.id
      kwargs['beam_id'] = self.beam.id
      kwargs['detector_id'] = self.detector.id
      kwargs['crystal_id'] = self.crystal.id
      kwargs['crystal_cell_id'] = self.crystal.cell_id

    db_proxy.__init__(self, app, "%s_experiment" % app.params.experiment_tag, id = experiment_id, **kwargs)
    self.experiment_id = self.id

    if experiment is None:
      self.imageset = Imageset(app, imageset_id=self.imageset_id)
      self.beam = Beam(app, beam_id=self.beam_id)
      self.detector = Detector(app, self.detector_id)
      self.crystal = Crystal(app, self.crystal_id)

class Imageset(db_proxy):
  def __init__(self, app, imageset_id = None, **kwargs):
    db_proxy.__init__(self, app, "%s_imageset" % app.params.experiment_tag, id=imageset_id, **kwargs)
    self.imageset_id = self.id

class Beam(db_proxy):
  def __init__(self, app, beam_id = None, beam = None, **kwargs):
    assert [beam_id, beam].count(None) == 1
    if beam is not None:
      u_s0 = beam.get_unit_s0()
      kwargs['direction_1'] = u_s0[0]
      kwargs['direction_2'] = u_s0[1]
      kwargs['direction_3'] = u_s0[2]
      kwargs['wavelength'] = beam.get_wavelength()

    db_proxy.__init__(self, app, "%s_beam" % app.params.experiment_tag, id=beam_id, **kwargs)
    self.beam_id = self.id

class Detector(db_proxy):
  def __init__(self, app, detector_id = None, detector = None, **kwargs):
    assert [detector_id, detector].count(None) == 1
    if detector is not None:
      kwargs['distance'] = flex.mean(flex.double([p.get_distance() for p in detector]))

    db_proxy.__init__(self, app, "%s_detector" % app.params.experiment_tag, id=detector_id, **kwargs)
    self.detector_id = self.id

class Crystal(db_proxy):
  def __init__(self, app, crystal_id = None, crystal = None, **kwargs):
    assert [crystal_id, crystal].count(None) == 1
    if crystal is not None:
      u = crystal.get_U() # orientation matrix
      for i in xrange(len(u)):
        kwargs['ori_%d'%(i+1)] = u[i]
      kwargs['mosaic_block_rotation'] = crystal._ML_half_mosaicity_deg
      kwargs['mosaic_block_size'] = crystal._ML_domain_size_ang

      self.cell = Cell(app, crystal=crystal)
      kwargs['cell_id'] = self.cell.id

    db_proxy.__init__(self, app, "%s_crystal" % app.params.experiment_tag, id=crystal_id, **kwargs)
    self.crystal_id = self.id

    if crystal is None:
      self.cell = Cell(app, cell_id = self.cell_id)

class Cell(db_proxy):
  def __init__(self, app, cell_id = None, crystal = None, **kwargs):
    assert [cell_id, crystal].count(None) == 1
    if crystal is not None:
      for key, p in zip(['a', 'b', 'c', 'alpha', 'beta', 'gamma'], crystal.get_unit_cell().parameters()):
        kwargs['cell_%s'%key] = p
      kwargs['lookup_symbol'] = crystal.get_space_group().type().lookup_symbol()
    db_proxy.__init__(self, app, "%s_cell" % app.params.experiment_tag, id=cell_id, **kwargs)
    self.cell_id = self.id

class Bin(db_proxy):
  def __init__(self, app, bin_id = None, **kwargs):
    db_proxy.__init__(self, app, "%s_bin" % app.params.experiment_tag, id=bin_id, **kwargs)
    self.bin_id = self.id

class Cell_Bin(db_proxy):
  def __init__(self, app, cell_bin_id = None, **kwargs):
    db_proxy.__init__(self, app, "%s_cell_bin" % app.params.experiment_tag, id=cell_bin_id, **kwargs)
    self.cell_bin_id = self.id
