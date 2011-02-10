
# This module is used by the PHENIX GUI to manage file objects and associated
# phil parameters.

# TODO better tests!  major functionality is tested as part of the handlers
# specific to HKL/PDB formats, but not every method yet

from iotbx import file_reader
from libtbx.utils import hashlib_md5
from libtbx import adopt_init_args, group_args
from libtbx.utils import Sorry
import os

class manager (object) :
  file_type = None
  file_type_label = None
  def __init__ (self,
                allowed_param_names=None,
                allowed_multiple_params=None,
                debug=False,
                auto_reload_files=True,
                use_md5_sum=False) :
    adopt_init_args(self, locals())
    assert ((allowed_param_names is None) or
            (isinstance(allowed_param_names, list)))
    assert ((allowed_multiple_params is None) or
            (isinstance(allowed_param_names, list)))
    self.clear_cache()
    self._param_callbacks = {}

  def clear_cache (self) :
    self._file_mtimes = {}
    self._file_md5sums = {}
    self._cached_input_files = {}
    self._param_files = {}
    self.clear_format_specific_cache()

  def clear_format_specific_cache (self) :
    pass

  def set_param_callback (self, file_param_name, callback_handler) :
    assert hasattr(callback_handler, "__call__")
    self._param_callbacks[file_param_name] = callback_handler

  def add_file_callback (self, file_name) :
    pass

  def remove_file_callback (self, file_name) :
    pass

  def input_files (self) :
    for (file_name, file_object) in self._cached_input_files.iteritems() :
      yield (file_name, file_object)

  def open_file (self, file_name) :
    input_file = file_reader.any_file(file_name)
    return input_file

  def save_file (self, input_file=None, file_name=None) :
    if (input_file is None) :
      input_file = self.open_file(file_name)
    input_file.assert_file_type(self.file_type)
    file_name = input_file.file_name
    self._cached_input_files[file_name] = input_file
    self.add_file_callback(file_name)
    if self.use_md5_sum :
      file_records = open(file_name).read()
      m = hashlib_md5(file_records)
      self._file_md5sums[file_name] = m
    else :
      mtime = os.path.getmtime(file_name)
      self._file_mtimes[file_name] = mtime
    return self.save_other_file_data(input_file)

  def add_file (self, *args, **kwds) :
    return self.save_file(*args, **kwds)

  def save_other_file_data (self, input_file) :
    return None

  def file_is_modified (self, file_name) :
    if (not self.auto_reload_files) :
      return False
    elif (not file_name in self._cached_input_files) :
      return True
    elif self.use_md5_sum :
      file_records = open(file_name).read()
      m = hashlib_md5(file_records)
      old_md5sum = self._file_md5sums.get(file_name, None)
      if (old_md5sum is None) or (old_md5sum != m) :
        self._file_md5sums[file_name] = m
        return True
    else :
      mtime = os.path.getmtime(file_name)
      old_mtime = self._file_mtimes.get(file_name, None)
      if (old_mtime is None) or (old_mtime < mtime) :
        self._file_mtimes[file_name] = mtime
        return True
    return False

  def remove_file (self, file_name) :
    if (file_name in self._cached_input_files) :
      self._cached_input_files.pop(file_name)
      if self.use_md5_sum :
        self._file_md5sums.pop(file_name)
      else :
        self._file_mtimes.pop(file_name)
      if (self.allowed_param_names is not None) :
        for param_name, param_file in self._param_files.iteritems() :
          if self.allow_multiple(param_name) :
            if (file_name in param_file) :
              param_file.remove(file_name)
              if (len(param_file) == 0 ) :
                self._param_files.pop(param_name)
              break
          elif (param_file == file_name) :
            self._param_files.pop(param_name)
            break
      self.remove_file_callback(file_name)

  def get_file (self, file_name=None, file_param_name=None) :
    if (file_name is None) and (file_param_name is not None) :
      file_name = self._param_files.get(file_param_name)
      if (isinstance(file_name, list)) :
        return file_name
    if (file_name is None) :
      return None
    assert os.path.isfile(file_name)
    if (file_name in self._cached_input_files) :
      if self.file_is_modified(file_name) :
        input_file = self.open_file(file_name)
        self.save_file(input_file)
      return self._cached_input_files[file_name]
    return None

  def allow_multiple (self, param_name) :
    if (self.allowed_multiple_params is not None) :
      return (param_name in self.allowed_multiple_params)
    return False

  def get_current_file_names (self) :
    file_names = self._cached_input_files.keys()
    file_names.sort()
    return file_names

  def set_param_file (self, file_name, file_param_name, input_file=None,
      run_callback=True) :
    if self.allowed_param_names is not None :
      if not file_param_name in self.allowed_param_names :
        raise KeyError("Unrecognized input file parameter %s."%file_param_name)
    opened_file = False
    if (file_name is None) or (file_name == "") or (file_name == "None") :
      self._param_files.pop(file_param_name, None)
    else :
      if (input_file is not None) :
        self.save_file(input_file)
      elif (self.get_file(file_name) is None) :
        input_file = self.open_file(file_name)
        opened_file = True
        self.save_file(input_file)
      if self.allow_multiple(file_param_name) :
        if (not file_param_name in self._param_files) :
          self._param_files[file_param_name] = []
        self._param_files[file_param_name].append(file_name)
      else :
        self._param_files[file_param_name] = file_name
    if run_callback :
      callback = self._param_callbacks.get(file_param_name, None)
      if (callback is not None) :
        callback(file_name)
    return opened_file

  def unset_param_file (self, file_name, file_param_name, run_callback=True) :
    if (self.allow_multiple(file_param_name) and
        (file_param_name in self._param_files)) :
      param_files = self._param_files.get(file_param_name)
      if (file_name in param_files) :
        param_files.remove(file_name)
      if (len(param_files) == 0) :
        self._param_files.pop(file_param_name)
    else :
      if (self._param_files[file_param_name] == file_name) :
        self._param_files.pop(file_param_name)
    if run_callback :
      callback = self._param_callbacks.get(file_param_name, None)
      if (callback is not None) :
        callback(None)

  def get_file_params (self, file_name) :
    params = []
    for file_param_name in self._param_files :
      param_files = self._param_files[file_param_name]
      if isinstance(param_files, list) and (file_name in param_files) :
        params.append(file_param_name)
      elif (param_files == file_name) :
        params.append(file_param_name)
    return params

  def get_param_files (self, file_param_name) :
    file_name = self._param_files.get(file_param_name)
    if (file_name is None) :
      return []
    elif isinstance(file_name, list) :
      return file_name
    else :
      return [ file_name ]

  def get_file_type_label (self, file_name=None, input_file=None) :
    return self.file_type_label

  def get_files_dict (self) :
    return self._cached_input_files

########################################################################

class symmetry_manager (object) :
  """
  Class for keeping track of symmetry information from multiple files.  This
  is particularly problematic in the phenix.refine GUI, where users may supply
  any number of PDB files as input, plus a PDB file representing a reference
  structure, and up to five reflection files.  Automatically taking the latest
  symmetry provided, without taking into account the symmetry information in
  other files and the current GUI state, may result in errors if files contain
  incompatible information.
  """
  def __init__ (self, prefer_pdb_space_group=True) :
    self.pdb_file_names = []
    self.reflection_file_names = []
    self.symmetry_by_file = {}
    self.current_space_group = None
    self.current_unit_cell = None
    self.prefer_pdb_space_group = prefer_pdb_space_group

  def set_current (self, space_group, unit_cell) :
    self.current_space_group = space_group
    self.current_unit_cell = unit_cell

  def get_current (self) :
    return (self.current_space_group, self.current_unit_cell)

  def get_current_as_strings (self) :
    sg, uc = self.get_current()
    if (uc is None) :
      uc_str = ""
    else :
      uc_str = "%.3g %.3g %.3g %.3g %.3g %.3g" % uc.parameters()
    if (sg is None) :
      sg_str = ""
    else :
      sg_str = str(sg)
    return (sg_str, uc_str)

  def set_current_as_strings (self, space_group, unit_cell) :
    """Set symmetry from fields in the GUI."""
    if (space_group == "") or (unit_cell is None) :
      self.current_space_group = None
    else :
      from cctbx import sgtbx
      try :
        self.current_space_group = sgtbx.space_group_info(space_group)
      except RuntimeError, e :
        if ("symbol not recognized" in str(e)) :
          raise Sorry(("The current value for the space group parameter, "+
            "'%s', could not be recognized as a valid space group symbol.") %
            space_group)
        else :
          raise
    if (unit_cell == "") or (unit_cell is None) :
      self.current_unit_cell = None
    else :
      from cctbx import uctbx
      self.current_unit_cell = uctbx.unit_cell(unit_cell)

  def process_pdb_file (self, input_file) :
    """Extract symmetry info from iotbx.file_reader._any_file object"""
    symm = input_file.file_object.crystal_symmetry()
    if (symm is not None) :
      space_group = symm.space_group_info()
      unit_cell = symm.unit_cell()
    else :
      space_group, unit_cell = None, None
    file_name = input_file.file_name
    return self.add_pdb_file(file_name, space_group, unit_cell)

  def add_pdb_file (self, file_name, space_group, unit_cell) :
    self.pdb_file_names.append(file_name)
    self.symmetry_by_file[file_name] = (space_group, unit_cell)
    return self.check_consistency_and_set_symmetry(
      file_name=file_name,
      space_group=space_group,
      unit_cell=unit_cell,
      file_type="pdb")

  def process_reflections_file (self, input_file) :
    """Extract symmetry info from iotbx.file_reader._any_file object"""
    symm = input_file.file_server.miller_arrays[0].crystal_symmetry()
    if (symm is not None) :
      space_group = symm.space_group_info()
      unit_cell = symm.unit_cell()
    else :
      space_group, unit_cell = None, None
    file_name = input_file.file_name
    return self.add_reflections_file(file_name, space_group, unit_cell)

  def add_reflections_file (self, file_name, space_group, unit_cell) :
    self.reflection_file_names.append(file_name)
    self.symmetry_by_file[file_name] = (space_group, unit_cell)
    return self.check_consistency_and_set_symmetry(
      file_name=file_name,
      space_group=space_group,
      unit_cell=unit_cell,
      file_type="hkl")

  def check_cell_compatibility (self, program_name,
      raise_error_if_incomplete=False) :
    if (self.current_unit_cell is None) or (self.current_space_group is None) :
      if (raise_error_if_incomplete) :
        raise Sorry("Either the unit cell or the space group (or both) is "+
          "not set; these parameters are required to run %s." % program_name)
      return None
    else :
      from cctbx import crystal
      try :
        symm = crystal.symmetry(space_group=self.current_space_group.group(),
          unit_cell=self.current_unit_cell)
      except AssertionError, e :
        raise Sorry("Unit cell parameters are not consistent with the "+
          "currently set space group.  Please make sure that the symmetry "+
          "information is entered correctly.")
      else :
        return True

  def check_consistency_and_set_symmetry (self, file_name, space_group,
      unit_cell, file_type) :
    space_group_mismatch = False
    set_new_space_group = False
    unit_cell_mismatch = False
    incompatible_cell = False
    if (space_group is not None) :
      if (self.current_space_group is not None) :
        current_sgname = str(self.current_space_group)
        new_sgname = str(space_group)
        if (current_sgname != new_sgname) :
          group = self.current_space_group.group()
          derived_sg = group.build_derived_point_group()
          if (space_group.group().build_derived_point_group() != derived_sg) :
            space_group_mismatch = True
          elif (file_type == "pdb") and (self.prefer_pdb_space_group) :
            self.current_space_group = space_group
      else :
        self.current_space_group = space_group
    if (unit_cell is not None) :
      if (self.current_unit_cell is not None) :
        if (not self.current_unit_cell.is_similar_to(unit_cell)) :
          unit_cell_mismatch = True
      else :
        self.current_unit_cell = unit_cell
    return (space_group_mismatch, unit_cell_mismatch)

  def get_symmetry_choices (self) :
    sg_files = []
    uc_files = []
    all_file_names = self.pdb_file_names + self.reflection_file_names
    for file_name in all_file_names :
      space_group, unit_cell = self.symmetry_by_file[file_name]
      if (space_group is not None) :
        sg_files.append((file_name, str(space_group)))
      if (unit_cell is not None) :
        uc_files.append((file_name, str(unit_cell)))
    return group_args(
      current_space_group=str(self.current_space_group),
      current_unit_cell=str(self.current_unit_cell),
      space_group_files=sg_files,
      unit_cell_files=uc_files)
