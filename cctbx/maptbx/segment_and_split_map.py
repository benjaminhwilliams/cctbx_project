from __future__ import division
import iotbx.phil
import iotbx.pdb
import iotbx.ccp4_map
from cctbx import crystal
from cctbx import maptbx
from libtbx.utils import Sorry
import sys, os
from cctbx.array_family import flex
from scitbx.math import matrix
from copy import deepcopy
from libtbx.utils import null_out

master_phil = iotbx.phil.parse("""

  input_files {

    seq_file = None
       .type = path
       .short_caption = Sequence file
       .help = Sequence file (unique chains only,  \
               1-letter code, chains separated by \
               blank line or greater-than sign.)  \
               Can have chains that are DNA/RNA/protein and\
               all can be present in one file.

    map_file = None
      .type = path
      .help = File with CCP4-style map
      .short_caption = Map file

    half_map_file = None
      .type = path
      .multiple = True
      .short_caption = Half map
      .help = Half map (two should be supplied) for FSC calculation. Must \
               have grid identical to map_file

    ncs_file = None
      .type = path
      .help = File with NCS information (typically point-group NCS with \
               the center specified). Typically in  PDB format. \
              Can also be a .ncs_spec file from phenix. \
              Created automatically if ncs_type is specified.
      .short_caption = NCS info file

    pdb_file = None
      .type = path
      .help = Optional PDB file matching map_file to be offset

    pdb_to_restore = None
      .type = path
      .help = Optional PDB file to restore to position matching original \
              map_file.  Used in combination with info_file=xxx.pkl \
              and restored_pdb=yyyy.pdb
      .short_caption = PDB to restore

    info_file = None
      .type = path
      .help = Optional pickle file with information from a previous run.\
              Can be used with pdb_to_restore to restore a PDB file to \
              to position matching original \
              map_file.
      .short_caption = Info file

    target_ncs_au_file = None
      .type = path
      .help = Optional PDB file to partially define the ncs asymmetric \
               unit of the map. The coordinates in this file will be used \
               to mark part of the ncs au and all points nearby that are \
               not part of another ncs au will be added.

     input_weight_map_pickle_file = None
       .type = path 
       .short_caption = Input weight map pickle file 
       .help = Weight map pickle file
  }

  output_files {

    magnification_map_file = magnification_map.ccp4
      .type = path
      .help = Input map file with magnification applied.  Only written if\
                magnification is applied.
      .short_caption = Magnification map file

    magnification_ncs_file = magnification_ncs.ncs_spec
      .type = path
      .help = Input NCS with magnification applied.  Only written if\
                magnification is applied.
      .short_caption = Magnification NCS file

    sharpening_map_file = sharpening_map.ccp4
      .type = path
      .help = Input map file with sharpening applied.  Only written if \
                sharpening is applied.
      .short_caption = Sharpened map file


    shifted_map_file = shifted_map.ccp4
      .type = path
      .help = Input map file shifted to new origin.
      .short_caption = Shifted map file

    shifted_sharpened_map_file = shifted_sharpened_map.ccp4
      .type = path
      .help = Input map file shifted to new origin and sharpened.
      .short_caption = Shifted sharpened map file

    shifted_pdb_file = shifted_pdb.pdb
      .type = path
      .help = Input pdb file shifted to new origin.
      .short_caption = Shifted pdb file

    shifted_ncs_file = shifted_ncs.ncs_spec
      .type = path
      .help = NCS information shifted to new origin.
      .short_caption = Output NCS info file

    shifted_used_ncs_file = shifted_used_ncs.ncs_spec
      .type = path
      .help = NCS information (just the part that is used) shifted \
               to new origin.
      .short_caption = Output used NCS info file

    output_directory = segmented_maps
      .type = path
      .help = Directory where output files are to be written \
                applied.
      .short_caption = Output directory

    box_map_file = box_map_au.ccp4
      .type = path
      .help = Output map file with one NCS asymmetric unit, cut out box
      .short_caption = Box NCS map file

    box_mask_file = box_mask_au.ccp4
      .type = path
      .help = Output mask file with one NCS asymmetric unit, cut out box
      .short_caption = Box NCS mask file

    box_buffer = 5
      .type = int
      .help = Buffer (grid units) around NCS asymmetric unit in box_mask and map
      .short_caption = Box buffer size

    au_output_file_stem = shifted_au
      .type = str
      .help = File stem for output map files with one NCS asymmetric unit
      .short_caption = Output au file stem

    write_intermediate_maps = False
      .type = bool
      .help = Write out intermediate maps and masks for visualization
      .short_caption = Write intermediate maps

    write_output_maps = True
      .type = bool
      .help = Write out maps
      .short_caption = Write maps

    remainder_map_file = remainder_map.ccp4
      .type = path
      .help = output map file with remainder after initial regions identified
      .short_caption = Output remainder map file

    output_info_file = segment_and_split_map_info.pkl
      .type = path
      .help = Output pickle file with information about map and masks
      .short_caption = Output pickle file

    restored_pdb = None
      .type = path
      .help = Output name of PDB restored to position matching original \
              map_file.  Used in combination with info_file=xxx.pkl \
              and pdb_to_restore=xxxx.pdb
      .short_caption = Restored PDB file

    output_weight_map_pickle_file = weight_map_pickle_file.pkl
       .type = path 
       .short_caption = Output weight map pickle file 
       .help = Output weight map pickle file
  }

  crystal_info {

     chain_type = *None PROTEIN RNA DNA
       .type = choice
       .short_caption = Chain type
       .help = Chain type. Determined automatically from sequence file if \
               not given. Mixed chain types are fine (leave blank if so).

     is_crystal = False
       .type = bool
       .short_caption = Is a crystal
       .help = Defines whether this is a crystal (or cryo-EM). Normally set \
                is_crystal along with use_sg_symmetry.

     use_sg_symmetry = False
       .type = bool
       .short_caption = Use space-group symmetry
       .help = If you set use_sg_symmetry=True then the symmetry of the space\
               group will be used. For example in P1 a point at one end of \
               the \
               unit cell is next to a point on the other end.  Normally for \
               cryo-EM data this should be set to False and for crystal data \
               it should be set to True.

     resolution = None
       .type = float
       .short_caption = resolution
       .help = Nominal resolution of the map. This is used later to decide on\
               resolution cutoffs for Fourier inversion of the map. Note: \
               the resolution is not cut at this value, it is cut at \
               resolution*d_min_ratio if at all.

     space_group = None
       .type = space_group
       .help = Space group (used for boxed maps)
       .style = hidden

     unit_cell = None
       .type = unit_cell
       .help = Unit Cell (used for boxed maps)
       .style = hidden

     solvent_content = None
       .type = float
       .help = Solvent fraction of the cell. Used for ID of \
               solvent content in boxed maps.
       .short_caption = Solvent content
       .style = hidden

     solvent_content_iterations = 3
       .type = int
       .help = Iterations of solvent fraction estimation. Used for ID of \
               solvent content in boxed maps.
       .short_caption = Solvent fraction iterations
       .style = hidden

     wang_radius = None
       .type = float
       .help = Wang radius for solvent identification. \
           Default is 1.5* resolution
       .short_caption = Wang radius 

     buffer_radius = None
       .type = float
       .help = Buffer radius for mask smoothing. \
           Default is resolution
       .short_caption = Buffer radius 

  }

  reconstruction_symmetry {

     ncs_type = None
       .type = str
       .short_caption = NCS type
       .help = Symmetry used in reconstruction. For example D7, C3, C2\
          I (icosahedral),T (tetrahedral), or ANY (try everything and \
          use the highest symmetry found). Not needed if ncs_file is supplied. \
          Note: ANY does not search for helical symmetry

     ncs_center = None
       .type = floats
       .short_caption = NCS center
       .help = Center (in A) for NCS operators (if ncs is found \
          automatically). \
          If set to None, first guess is the center of the cell and then \
          if that fails, found automatically as the center of the \
          density in the map.

     optimize_center = None
       .type = bool
       .short_caption = Optimize NCS center
       .help = Optimize position of NCS center. Default is False \
           if ncs_center is supplied or center of map is used and \
           True if it is found automatically).

     helical_rot_deg = None
       .type = float
       .short_caption = helical rotation
       .help = helical rotation about z in degrees

     helical_trans_z_angstrom = None
       .type = float
       .short_caption = helical translation
       .help = helical translation along z in Angstrom units

     two_fold_along_x = None
       .type = bool
       .short_caption = D two-fold along x
       .help = Specifies if D or I two-fold is along x (True) or y (False). \
               If None, both are tried.

     random_points = 100
       .type = int
       .short_caption = Random points
       .help = Number of random points in map to examine in finding NCS

     n_rescore = 5
       .type = int
       .short_caption = NCS operators to rescore
       .help = Number of NCS operators to rescore

     op_max = 14
       .type = int
       .short_caption = Max operators to try
       .help = If ncs_type is ANY, try up to op_max-fold symmetries
     }

  map_modification {

     magnification = None
       .type = float
       .short_caption = Magnification
       .help = Magnification to apply to input map.  Input map grid will be \
                scaled by magnification factor before anything else is done.

     b_iso = None
       .type = float
       .short_caption = Target b_iso
       .help = Target B-value for map (sharpening will be applied to yield \
          this value of b_iso)

     b_sharpen = None
       .type = float
       .short_caption = Sharpening
       .help = Sharpen with this b-value. Contrast with b_iso that yield a \
           targeted value of b_iso

     resolution_dependent_b = None
       .type = floats
       .short_caption = resolution_dependent b
       .help = If set, apply resolution_dependent_b (b0 b1 b2). \
             Log10(amplitudes) will start at 1, change to b0 at half \
             of resolution specified, changing linearly, \
             change to b1 at resolution specified, \
             and change to b2 at high-resolution limit of map

     d_min_ratio = 0.833
       .type = float
       .short_caption = Sharpen d_min ratio
       .help = Sharpening will be applied using d_min equal to \
             d_min_ratio times resolution. If None, box of reflections \
             with the same grid as the map used.

     rmsd = None
       .type = float
       .short_caption = RMSD of model
       .help = RMSD of model to true model (if supplied).  Used to \
             estimate expected fall-of with resolution of correct part \
             of model-based map. If None, assumed to be resolution/3.

     fraction_complete = None
       .type = float
       .short_caption = Completeness model
       .help = Completness of model (if supplied).  Used to \
             estimate correct part \
             of model-based map. If None, estimated from max(FSC).

     auto_sharpen = True
       .type = bool
       .short_caption = Automatically determine sharpening
       .help = Automatically determine sharpening using kurtosis maximization\
                 or adjusted surface area

     auto_sharpen_methods = *no_sharpening *b_iso *b_iso_to_d_cut \
                            *resolution_dependent model_sharpening \
                             half_map_sharpening None
       .type = choice(multi=True)
       .short_caption = Sharpening methods
       .help = Methods to use in sharpening. b_iso searches for b_iso to \
          maximize sharpening target (kurtosis or adjusted_sa). \
          b_iso_to_d_cut applies b_iso only up to resolution specified, with \
          fall-over of k_sharpen.  Resolution dependent adjusts 3 parameters \
          to sharpen variably over resolution range.

     box_in_auto_sharpen = True
       .type = bool
       .short_caption = Use box for auto_sharpening
       .help = Use a representative box of density for initial \
                auto-sharpening instead of the entire map.

    soft_mask = False
      .type = bool
      .help = Use soft mask (smooth change from inside to outside with radius\
             based on resolution of map). In development
      .short_caption = Soft mask

     use_weak_density = False
       .type = bool
       .short_caption = Use box with poor density
       .help = When choosing box of representative density, use poor \
               density (to get optimized map for weaker density)

     discard_if_worse = True
       .type = bool
       .short_caption = Discard sharpening if worse
       .help = Discard sharpening if worse

     local_sharpening = None
       .type = bool
       .short_caption = Local sharpening
       .help = Sharpen locally using overlapping regions. \
               NOTE: Best to turn off local_aniso_in_local_sharpening \
               if NCS is present.\
               If local_aniso_in_local_sharpening is True and NCS is \
               present this can distort the map for some NCS copies \
               because an anisotropy correction is applied\
               based on local density in one copy and is transferred without \
               rotation to other copies.

     local_aniso_in_local_sharpening = None
       .type = bool
       .short_caption = Local anisotropy 
       .help = Use local anisotropy in local sharpening.  \
               Default is True unless NCS is present.

     select_sharpened_map = None
       .type = int
       .short_caption = Sharpened map to use
       .help = Select a single sharpened map to use

     read_sharpened_maps = None
       .type = bool 
       .short_caption = Read sharpened maps
       .help = Read in previously-calculated sharpened maps

     write_sharpened_maps = None
       .type = bool 
       .short_caption = Write sharpened maps
       .help = Write out local sharpened maps

     smoothing_radius = None
       .type = float 
       .short_caption = Smoothing radius 
       .help = Sharpen locally using smoothing_radius. Default is 2/3 of \
                 mean distance between centers for sharpening

     box_center = None
       .type = floats
       .short_caption = Center of box
       .help = You can specify the center of the box (A units)

     box_size = 40 40 40
       .type = ints
       .short_caption = Size of box
       .help = You can specify the size of the box (grid units) 

     remove_aniso = True
       .type = bool
       .short_caption = Remove aniso 
       .help = You can remove anisotropy (overall and locally) during sharpening

     max_box_fraction = 0.5
       .type = float
       .short_caption = Max size of box for auto_sharpening
       .help = If box is greater than this fraction of entire map, use \
                entire map.

     mask_atoms = True
       .type = bool
       .short_caption = Mask atoms 
       .help = Mask atoms when using model sharpening

     mask_atoms_atom_radius = 3
       .type =float
       .short_caption = Mask radius
       .help = Mask for mask_atoms will have mask_atoms_atom_radius

     value_outside_atoms = None
       .type = str
       .short_caption = Value outside atoms
       .help = Value of map outside atoms (set to 'mean' to have mean \
                value inside and outside mask be equal)

     k_sharpen = 10
       .type = float
       .short_caption = sharpening transition
       .help = Steepness of transition between sharpening (up to resolution \
           ) and not sharpening (d < resolution).  Note: for blurring, \
           all data are blurred (regardless of resolution), while for \
           sharpening, only data with d about resolution or lower are \
           sharpened. This prevents making very high-resolution data too \
           strong.  Note 2: if k_sharpen is zero, then no \
           transition is applied and all data is sharpened or blurred. \
           Note 3: only used if b_iso is set.

     maximum_low_b_adjusted_sa = 0.
       .type = float
       .short_caption = Max low-B adjusted_sa
       .help = Require adjusted surface area to be this value or less \
               when map is highly sharpened (at value of search_b_min).

     search_b_min = -100
       .type = float
       .short_caption = Low bound for b_iso search
       .help = Low bound for b_iso search.

     search_b_max = 300
       .type = float
       .short_caption = High bound for b_iso search
       .help = High bound for b_iso search.

     search_b_n = 21
       .type = int
       .short_caption = Number of b_iso values to search
       .help = Number of b_iso values to search.

     residual_target = 'adjusted_sa'
       .type = str
       .short_caption = Residual target
       .help = Target for maximization steps in sharpening.  \
          Can be kurtosis or adjusted_sa (adjusted surface area)

     sharpening_target = 'adjusted_sa'
       .type = str
       .short_caption = Overall sharpening target
       .help = Overall target for sharpening.  Can be kurtosis or adjusted_sa \
          (adjusted surface area).  Used to decide which sharpening approach \
          is used. Note that during optimization, residual_target is used \
          (they can be the same.)

     require_improvement = True
       .type = bool
       .short_caption = Require improvement
       .help = Require improvement in score for sharpening to be applied

     region_weight = 40
       .type = float
       .short_caption = Region weighting
       .help = Region weighting in adjusted surface area calculation.\
            Score is surface area minus region_weight times number of regions.\
            Default is 40. A smaller value will give more sharpening.

     sa_percent = 30.
       .type = float
       .short_caption = Percent of target regions in adjusted_sa
       .help = Percent of target regions used in calulation of adjusted \
         surface area.  Default is 30.

     fraction_occupied = 0.20
       .type = float
       .short_caption = Fraction of molecular volume inside contours
       .help = Fraction of molecular volume targeted to be inside contours. \
           Used to set contour level. Default is 0.20

      n_bins = 20
        .type = int
        .short_caption = Resolution bins
        .help = Number of resolution bins for sharpening. Default is 20.

      max_regions_to_test = 30
        .type = int
        .short_caption = Max regions to test
        .help = Number of regions to test for surface area in adjusted_sa \
                scoring of sharpening

      eps = None
        .type = float
        .short_caption = Shift used in calculation of derivatives for \
           sharpening maximization.  Default is 0.01 for kurtosis and 0.5 for \
           adjusted_sa.

      k_sol = 0.35
        .type = float
        .help = k_sol value for model map calculation
        .short_caption = k_sol
  
      b_sol = 50
        .type = float
        .help = b_sol value for model map calculation
        .short_caption = b_sol
  }

  segmentation {

    density_select = True
      .type = bool
      .help = Run map_box with density_select=True to cut out the region \
              in the input map that contains density. Useful if the input map \
              is much larger than the structure. Done before segmentation is\
              carried out.
      .short_caption = Trim map to density

    density_select_threshold = 0.05
      .type = float
      .help = Choose region where density is this fraction of maximum or greater
      .short_caption = threshold for density_select

    get_half_height_width = None
      .type = bool
      .help = Use 4 times half-width at half-height as estimate of max size
      .short_caption = Half-height width estimation 

    mask_threshold = None
      .type = float
      .help = threshold in identification of overall mask. If None, guess \
               volume of molecule from sequence and NCS copies.
      .short_caption = Density select threshold

    grid_spacing_for_au = 3
      .type = int
      .help = Grid spacing for asymmetric unit when constructing asymmetric unit.
      .short_caption = Grid spacing for constructing asymmetric unit

    radius = None
      .type = float
      .help = Radius for constructing asymmetric unit.
      .short_caption = Radius for constructing asymmetric unit


    value_outside_mask = 0.0
      .type = float
      .help = Value to assign to density outside masks
      .short_caption = Value outside mask

    density_threshold = None
      .type = float
      .short_caption = Density threshold
      .help = Threshold density for identifying regions of density. \
             Applied after normalizing the density in the region of \
             the molecule to an rms of 1 and mean of zero.

    starting_density_threshold = None
      .type = float
      .short_caption = Starting density threshold
      .help = Optional guess of threshold density

    max_overlap_fraction = 0.05
      .type = float
      .short_caption = Max overlap
      .help = Maximum fractional overlap allowed to density in another \
              asymmetric unit. Definition of a bad region.

    remove_bad_regions_percent = 1
      .type = float
      .short_caption = Remove worst overlapping regions
      .help = Remove the worst regions that are part of more than one NCS \
           asymmetric unit, up to remove_bad_regions_percent of the total

    require_complete = True
      .type = bool
      .short_caption = Require all NCS copies to be represented for a region
      .help =  Require all NCS copies to be represented for a region

    split_if_possible = True
      .type = bool
      .short_caption = Split regions if mixed
      .help = Split regions that are split in some NCS copies.\
              If None, split if most copies are split.

    write_all_regions = False
      .type = bool
      .short_caption = Write all regions
      .help = Write all regions to ccp4 map files.

    fraction_occupied = 0.2
      .type = float
      .help = Fraction of volume inside macromolecule that should be above \
             threshold density
      .short_caption = Fraction occupied

    max_per_au = None
      .type = int
      .short_caption = Max regions in au
      .help = Maximum number of regions to be kept in the NCS asymmetric unit

    max_per_au_ratio = 5.
      .type = int
      .short_caption = Max ratio of regions to expected
      .help = Maximum ratio of number of regions to be kept in the \
         NCS asymmetric unit to those expected

    min_ratio_of_ncs_copy_to_first = 0.5
      .type = float
      .short_caption = Minimum ratio of ncs copy to first
      .help = Minimum ratio of the last ncs_copy region size to maximum

    min_ratio = 0.1
      .type = float
      .short_caption = Minimum ratio to keep
      .help = Minimum ratio of region size to maximum to keep it

    max_ratio_to_target = 3
      .type = float
      .help = Maximum ratio of grid points in top region to target
      .short_caption = Max ratio to target

    min_ratio_to_target = 0.3
      .type = float
      .help = Minimum ratio of grid points in top region to target
      .short_caption = Min ratio to target

    min_volume = 10
      .type = int
      .help = Minimum region size to consider (in grid points)
      .short_caption = Minimum region size

    residues_per_region = 50
      .type = float
      .help = Target number of residues per region
      .short_caption = Residues per region

    seeds_to_try = 10
      .type = int
      .help = Number of regions to try as centers
      .short_caption = Seeds to try

    iterate_with_remainder = True
      .type = bool
      .short_caption = Iterate
      .help = Iterate looking for regions based on remainder from first analysis

    weight_rad_gyr = 0.1
      .type = float
      .short_caption = Weight on radius of gyration
      .help = Weight on radius of gyration of group of regions in NCS AU \
               relative to weight on closeness to neighbors.  Normalized to\
               largest cell dimension with weight=weight_rad_gyr*300/cell_max

    expand_size = None
      .type = int
      .help = Grid points to expand size of regions when excluding for next \
               round. If None, set to approx number of grid points to get \
               expand_target below
      .short_caption = Expand size

    expand_target = 1.5
      .type = float
      .help = Target expansion of regions (A)
      .short_caption = Expand target

    mask_additional_expand_size = 1
      .type = int
      .help = Mask expansion in addition to expand_size for final map
      .short_caption = Mask additional expansion

    exclude_points_in_ncs_copies = True
      .type = bool
      .help = Exclude points that are in NCS copies when creating NCS au. \
               Does not apply if add_neighbors=True
      .short_caption = Exclude points in NCS copies

    add_neighbors = True
      .type = bool
      .help = Add neighboring regions around the NCS au. Turns off \
           exclude_points_in_ncs_copies also.
      .short_caption = Add neighbors 

    add_neighbors_dist = 1.
      .type = float
      .help = Max increase in radius of gyration by adding region to keep it.
      .short_caption = Add neighbors dist
  }

   control {
     verbose = False
        .type = bool
        .help = '''Verbose output'''
        .short_caption = Verbose output

     sharpen_only = None
        .type = bool
        .short_caption = Sharpen only
        .help = Sharpen map and stop

     resolve_size = None
        .type = int
        .help = "Size of resolve to use. "
        .style = hidden
   }
""", process_includes=True)
master_params = master_phil

# Symmetry for icosahedron
icosahedral_text=\
"""
REMARK 350   BIOMT1   1  1.000000  0.000000 -0.000000        0.00000
REMARK 350   BIOMT2   1 -0.000000  1.000000  0.000000        0.00000
REMARK 350   BIOMT3   1 -0.000000  0.000000  1.000000        0.00000
REMARK 350   BIOMT1   2  0.309017 -0.951056 -0.000132        0.00000
REMARK 350   BIOMT2   2  0.951057  0.309017  0.000181        0.00000
REMARK 350   BIOMT3   2 -0.000132 -0.000181  1.000000        0.00000
REMARK 350   BIOMT1   3 -0.809017 -0.587785 -0.000344        0.00000
REMARK 350   BIOMT2   3  0.587785 -0.809017  0.000112        0.00000
REMARK 350   BIOMT3   3 -0.000344 -0.000112  1.000000        0.00000
REMARK 350   BIOMT1   4 -0.809017  0.587785 -0.000344        0.00000
REMARK 350   BIOMT2   4 -0.587785 -0.809017 -0.000112        0.00000
REMARK 350   BIOMT3   4 -0.000344  0.000112  1.000000        0.00000
REMARK 350   BIOMT1   5  0.309017  0.951056 -0.000132        0.00000
REMARK 350   BIOMT2   5 -0.951057  0.309017 -0.000181        0.00000
REMARK 350   BIOMT3   5 -0.000132  0.000181  1.000000        0.00000
REMARK 350   BIOMT1   6 -0.947319 -0.162298  0.276128        0.00000
REMARK 350   BIOMT2   6 -0.162298 -0.500000 -0.850682        0.00000
REMARK 350   BIOMT3   6  0.276128 -0.850682  0.447319        0.00000
REMARK 350   BIOMT1   7 -0.447128  0.850751  0.276223        0.00000
REMARK 350   BIOMT2   7 -0.525569  0.000000 -0.850751        0.00000
REMARK 350   BIOMT3   7 -0.723777 -0.525569  0.447128        0.00000
REMARK 350   BIOMT1   8  0.670906  0.688091  0.276436        0.00000
REMARK 350   BIOMT2   8 -0.162298  0.500000 -0.850682        0.00000
REMARK 350   BIOMT3   8 -0.723564  0.525862  0.447128        0.00000
REMARK 350   BIOMT1   9  0.861698 -0.425487  0.276472        0.00000
REMARK 350   BIOMT2   9  0.425487  0.309017 -0.850570        0.00000
REMARK 350   BIOMT3   9  0.276472  0.850570  0.447319        0.00000
REMARK 350   BIOMT1  10 -0.138420 -0.951056  0.276282        0.00000
REMARK 350   BIOMT2  10  0.425487 -0.309017 -0.850570        0.00000
REMARK 350   BIOMT3  10  0.894316 -0.000181  0.447437        0.00000
REMARK 350   BIOMT1  11 -0.861698 -0.425487 -0.276472        0.00000
REMARK 350   BIOMT2  11 -0.425487  0.309017  0.850570        0.00000
REMARK 350   BIOMT3  11 -0.276472  0.850570 -0.447319        0.00000
REMARK 350   BIOMT1  12 -0.670906  0.688091 -0.276436        0.00000
REMARK 350   BIOMT2  12  0.162298  0.500000  0.850682        0.00000
REMARK 350   BIOMT3  12  0.723564  0.525862 -0.447128        0.00000
REMARK 350   BIOMT1  13  0.447128  0.850751 -0.276223        0.00000
REMARK 350   BIOMT2  13  0.525569 -0.000000  0.850751        0.00000
REMARK 350   BIOMT3  13  0.723777 -0.525569 -0.447128        0.00000
REMARK 350   BIOMT1  14  0.947319 -0.162298 -0.276128        0.00000
REMARK 350   BIOMT2  14  0.162298 -0.500000  0.850682        0.00000
REMARK 350   BIOMT3  14 -0.276128 -0.850682 -0.447319        0.00000
REMARK 350   BIOMT1  15  0.138420 -0.951056 -0.276282        0.00000
REMARK 350   BIOMT2  15 -0.425487 -0.309017  0.850570        0.00000
REMARK 350   BIOMT3  15 -0.894316 -0.000181 -0.447437        0.00000
REMARK 350   BIOMT1  16  0.809017  0.587785  0.000344        0.00000
REMARK 350   BIOMT2  16  0.587785 -0.809017  0.000112        0.00000
REMARK 350   BIOMT3  16  0.000344  0.000112 -1.000000        0.00000
REMARK 350   BIOMT1  17  0.809017 -0.587785  0.000344        0.00000
REMARK 350   BIOMT2  17 -0.587785 -0.809017 -0.000112        0.00000
REMARK 350   BIOMT3  17  0.000344 -0.000112 -1.000000        0.00000
REMARK 350   BIOMT1  18 -0.309017 -0.951056  0.000132        0.00000
REMARK 350   BIOMT2  18 -0.951057  0.309017 -0.000181        0.00000
REMARK 350   BIOMT3  18  0.000132 -0.000181 -1.000000        0.00000
REMARK 350   BIOMT1  19 -1.000000  0.000000  0.000000        0.00000
REMARK 350   BIOMT2  19  0.000000  1.000000  0.000000        0.00000
REMARK 350   BIOMT3  19 -0.000000  0.000000 -1.000000        0.00000
REMARK 350   BIOMT1  20 -0.309017  0.951056  0.000132        0.00000
REMARK 350   BIOMT2  20  0.951057  0.309017  0.000181        0.00000
REMARK 350   BIOMT3  20  0.000132  0.000181 -1.000000        0.00000
REMARK 350   BIOMT1  21 -0.138420 -0.425487  0.894316        0.00000
REMARK 350   BIOMT2  21  0.951057 -0.309017  0.000181        0.00000
REMARK 350   BIOMT3  21  0.276282  0.850570  0.447437        0.00000
REMARK 350   BIOMT1  22 -0.447554 -0.000000  0.894257        0.00000
REMARK 350   BIOMT2  22 -0.000000 -1.000000 -0.000000        0.00000
REMARK 350   BIOMT3  22  0.894257 -0.000000  0.447554        0.00000
REMARK 350   BIOMT1  23 -0.138420  0.425487  0.894316        0.00000
REMARK 350   BIOMT2  23 -0.951057 -0.309017 -0.000181        0.00000
REMARK 350   BIOMT3  23  0.276282 -0.850570  0.447437        0.00000
REMARK 350   BIOMT1  24  0.361771  0.262966  0.894411        0.00000
REMARK 350   BIOMT2  24 -0.587785  0.809017 -0.000112        0.00000
REMARK 350   BIOMT3  24 -0.723623 -0.525681  0.447246        0.00000
REMARK 350   BIOMT1  25  0.361771 -0.262966  0.894411        0.00000
REMARK 350   BIOMT2  25  0.587785  0.809017  0.000112        0.00000
REMARK 350   BIOMT3  25 -0.723623  0.525681  0.447246        0.00000
REMARK 350   BIOMT1  26  0.447128 -0.525569  0.723777        0.00000
REMARK 350   BIOMT2  26 -0.850751  0.000000  0.525569        0.00000
REMARK 350   BIOMT3  26 -0.276223 -0.850751 -0.447128        0.00000
REMARK 350   BIOMT1  27 -0.361771 -0.587785  0.723623        0.00000
REMARK 350   BIOMT2  27 -0.262966  0.809017  0.525681        0.00000
REMARK 350   BIOMT3  27 -0.894411 -0.000112 -0.447246        0.00000
REMARK 350   BIOMT1  28 -0.670906  0.162298  0.723564        0.00000
REMARK 350   BIOMT2  28  0.688091  0.500000  0.525862        0.00000
REMARK 350   BIOMT3  28 -0.276436  0.850682 -0.447128        0.00000
REMARK 350   BIOMT1  29 -0.053062  0.688091  0.723682        0.00000
REMARK 350   BIOMT2  29  0.688091 -0.500000  0.525862        0.00000
REMARK 350   BIOMT3  29  0.723682  0.525862 -0.446938        0.00000
REMARK 350   BIOMT1  30  0.637921  0.262966  0.723813        0.00000
REMARK 350   BIOMT2  30 -0.262966 -0.809017  0.525681        0.00000
REMARK 350   BIOMT3  30  0.723813 -0.525681 -0.446938        0.00000
REMARK 350   BIOMT1  31  0.053062  0.688091 -0.723682        0.00000
REMARK 350   BIOMT2  31 -0.688091 -0.500000 -0.525862        0.00000
REMARK 350   BIOMT3  31 -0.723682  0.525862  0.446938        0.00000
REMARK 350   BIOMT1  32  0.670906  0.162298 -0.723564        0.00000
REMARK 350   BIOMT2  32 -0.688091  0.500000 -0.525862        0.00000
REMARK 350   BIOMT3  32  0.276436  0.850682  0.447128        0.00000
REMARK 350   BIOMT1  33  0.361771 -0.587785 -0.723623        0.00000
REMARK 350   BIOMT2  33  0.262966  0.809017 -0.525681        0.00000
REMARK 350   BIOMT3  33  0.894411 -0.000112  0.447246        0.00000
REMARK 350   BIOMT1  34 -0.447128 -0.525569 -0.723777        0.00000
REMARK 350   BIOMT2  34  0.850751  0.000000 -0.525569        0.00000
REMARK 350   BIOMT3  34  0.276223 -0.850751  0.447128        0.00000
REMARK 350   BIOMT1  35 -0.637921  0.262966 -0.723813        0.00000
REMARK 350   BIOMT2  35  0.262966 -0.809017 -0.525681        0.00000
REMARK 350   BIOMT3  35 -0.723813 -0.525681  0.446938        0.00000
REMARK 350   BIOMT1  36 -0.361771  0.262966 -0.894411        0.00000
REMARK 350   BIOMT2  36  0.587785  0.809017  0.000112        0.00000
REMARK 350   BIOMT3  36  0.723623 -0.525681 -0.447246        0.00000
REMARK 350   BIOMT1  37  0.138420  0.425487 -0.894316        0.00000
REMARK 350   BIOMT2  37  0.951057 -0.309017  0.000181        0.00000
REMARK 350   BIOMT3  37 -0.276282 -0.850570 -0.447437        0.00000
REMARK 350   BIOMT1  38  0.447554 -0.000000 -0.894257        0.00000
REMARK 350   BIOMT2  38 -0.000000 -1.000000  0.000000        0.00000
REMARK 350   BIOMT3  38 -0.894257  0.000000 -0.447554        0.00000
REMARK 350   BIOMT1  39  0.138420 -0.425487 -0.894316        0.00000
REMARK 350   BIOMT2  39 -0.951057 -0.309017 -0.000181        0.00000
REMARK 350   BIOMT3  39 -0.276282  0.850570 -0.447437        0.00000
REMARK 350   BIOMT1  40 -0.361771 -0.262966 -0.894411        0.00000
REMARK 350   BIOMT2  40 -0.587785  0.809017 -0.000112        0.00000
REMARK 350   BIOMT3  40  0.723623  0.525681 -0.447246        0.00000
REMARK 350   BIOMT1  41 -0.138420  0.951056  0.276282        0.00000
REMARK 350   BIOMT2  41 -0.425487 -0.309017  0.850570        0.00000
REMARK 350   BIOMT3  41  0.894316  0.000181  0.447437        0.00000
REMARK 350   BIOMT1  42  0.861698  0.425487  0.276472        0.00000
REMARK 350   BIOMT2  42 -0.425487  0.309017  0.850570        0.00000
REMARK 350   BIOMT3  42  0.276472 -0.850570  0.447319        0.00000
REMARK 350   BIOMT1  43  0.670906 -0.688091  0.276436        0.00000
REMARK 350   BIOMT2  43  0.162298  0.500000  0.850682        0.00000
REMARK 350   BIOMT3  43 -0.723564 -0.525862  0.447128        0.00000
REMARK 350   BIOMT1  44 -0.447128 -0.850751  0.276223        0.00000
REMARK 350   BIOMT2  44  0.525569 -0.000000  0.850751        0.00000
REMARK 350   BIOMT3  44 -0.723777  0.525569  0.447128        0.00000
REMARK 350   BIOMT1  45 -0.947319  0.162298  0.276128        0.00000
REMARK 350   BIOMT2  45  0.162298 -0.500000  0.850682        0.00000
REMARK 350   BIOMT3  45  0.276128  0.850682  0.447319        0.00000
REMARK 350   BIOMT1  46  0.053062 -0.688091 -0.723682        0.00000
REMARK 350   BIOMT2  46  0.688091 -0.500000  0.525862        0.00000
REMARK 350   BIOMT3  46 -0.723682 -0.525862  0.446938        0.00000
REMARK 350   BIOMT1  47 -0.637921 -0.262966 -0.723813        0.00000
REMARK 350   BIOMT2  47 -0.262966 -0.809017  0.525681        0.00000
REMARK 350   BIOMT3  47 -0.723813  0.525681  0.446938        0.00000
REMARK 350   BIOMT1  48 -0.447128  0.525569 -0.723777        0.00000
REMARK 350   BIOMT2  48 -0.850751 -0.000000  0.525569        0.00000
REMARK 350   BIOMT3  48  0.276223  0.850751  0.447128        0.00000
REMARK 350   BIOMT1  49  0.361771  0.587785 -0.723623        0.00000
REMARK 350   BIOMT2  49 -0.262966  0.809017  0.525681        0.00000
REMARK 350   BIOMT3  49  0.894411  0.000112  0.447246        0.00000
REMARK 350   BIOMT1  50  0.670906 -0.162298 -0.723564        0.00000
REMARK 350   BIOMT2  50  0.688091  0.500000  0.525862        0.00000
REMARK 350   BIOMT3  50  0.276436 -0.850682  0.447128        0.00000
REMARK 350   BIOMT1  51 -0.361771  0.587785  0.723623        0.00000
REMARK 350   BIOMT2  51  0.262966  0.809017 -0.525681        0.00000
REMARK 350   BIOMT3  51 -0.894411  0.000112 -0.447246        0.00000
REMARK 350   BIOMT1  52  0.447128  0.525569  0.723777        0.00000
REMARK 350   BIOMT2  52  0.850751 -0.000000 -0.525569        0.00000
REMARK 350   BIOMT3  52 -0.276223  0.850751 -0.447128        0.00000
REMARK 350   BIOMT1  53  0.637921 -0.262966  0.723813        0.00000
REMARK 350   BIOMT2  53  0.262966 -0.809017 -0.525681        0.00000
REMARK 350   BIOMT3  53  0.723813  0.525681 -0.446938        0.00000
REMARK 350   BIOMT1  54 -0.053062 -0.688091  0.723682        0.00000
REMARK 350   BIOMT2  54 -0.688091 -0.500000 -0.525862        0.00000
REMARK 350   BIOMT3  54  0.723682 -0.525862 -0.446938        0.00000
REMARK 350   BIOMT1  55 -0.670906 -0.162298  0.723564        0.00000
REMARK 350   BIOMT2  55 -0.688091  0.500000 -0.525862        0.00000
REMARK 350   BIOMT3  55 -0.276436 -0.850682 -0.447128        0.00000
REMARK 350   BIOMT1  56  0.447128 -0.850751 -0.276223        0.00000
REMARK 350   BIOMT2  56 -0.525569  0.000000 -0.850751        0.00000
REMARK 350   BIOMT3  56  0.723777  0.525569 -0.447128        0.00000
REMARK 350   BIOMT1  57 -0.670906 -0.688091 -0.276436        0.00000
REMARK 350   BIOMT2  57 -0.162298  0.500000 -0.850682        0.00000
REMARK 350   BIOMT3  57  0.723564 -0.525862 -0.447128        0.00000
REMARK 350   BIOMT1  58 -0.861698  0.425487 -0.276472        0.00000
REMARK 350   BIOMT2  58  0.425487  0.309017 -0.850570        0.00000
REMARK 350   BIOMT3  58 -0.276472 -0.850570 -0.447319        0.00000
REMARK 350   BIOMT1  59  0.138420  0.951056 -0.276282        0.00000
REMARK 350   BIOMT2  59  0.425487 -0.309017 -0.850570        0.00000
REMARK 350   BIOMT3  59 -0.894316  0.000181 -0.447437        0.00000
REMARK 350   BIOMT1  60  0.947319  0.162298 -0.276128        0.00000
REMARK 350   BIOMT2  60 -0.162298 -0.500000 -0.850682        0.00000
REMARK 350   BIOMT3  60 -0.276128  0.850682 -0.447319        0.00000
"""


class pdb_info_object:
  def __init__(self,
    file_name=None,
    n_residues=None,
    ):
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    import time
    self.init_asctime=time.asctime()

  def show_summary(self,out=sys.stdout):
    print >>out,"PDB file:%s" %(self.file_name),
    if self.n_residues:
      print >>out,"   Residues: %d" %(self.n_residues)
    else:
      print >>out

class seq_info_object:
  def __init__(self,
    file_name=None,
    n_residues=None,
    ):
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    import time
    self.init_asctime=time.asctime()

  def show_summary(self,out=sys.stdout):
    print >>out,"Sequence file:%s" %(self.file_name),
    if self.n_residues:
      print >>out,"   Residues: %d" %(self.n_residues)
    else:
      print >>out


class ncs_info_object:
  def __init__(self,
    file_name=None,
    number_of_operators=None,
    is_helical_symmetry=None,
    original_number_of_operators=None,
    ):
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    import time
    self.init_asctime=time.asctime()
    if original_number_of_operators is None:
       self.original_number_of_operators=number_of_operators

    self._has_updated_operators=False

  def show_summary(self,out=sys.stdout):
    print >>out,"NCS file:%s   Operators: %d" %(self.file_name,
      self.number_of_operators)
    if self.is_helical_symmetry:
      print >>out,"Helical symmetry is present"

  def has_updated_operators(self):
    return self._has_updated_operators

  def update_number_of_operators(self,number_of_operators=None):
    self.number_of_operators=number_of_operators
    self._has_updated_operators=True

  def update_is_helical_symmetry(self,is_helical_symmetry=None):
    self.is_helical_symmetry=is_helical_symmetry
    self._has_updated_operators=True


class map_info_object:
  def __init__(self,
    file_name=None,
    origin=None,
    all=None,
    crystal_symmetry=None,
    is_map=None,
    map_id=None,
    b_sharpen=None,
    id=None,
    ):
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    import time
    self.init_asctime=time.asctime()

  def show_summary(self,out=sys.stdout):
    if self.is_map:
      print >>out,"Map file:%s" %(self.file_name),
    else:
      print >>out,"Mask file:%s" %(self.file_name),
    if self.id is not None:
      print >>out,"ID: %d" %(self.id),
    if self.b_sharpen is not None:
      print >>out,"B-sharpen: %7.2f" %(self.b_sharpen),
    if self.map_id is not None:
      print >>out,"Map ID: %s" %(self.map_id)
    else:
      print >>out
    if self.origin and self.all:
      print >>out,"   Origin: %d  %d  %d   Extent: %d  %d  %d" %(
       tuple(self.origin)+tuple(self.all))
    if self.crystal_symmetry:
      print >>out,"   Map unit cell: %.1f  %.1f  %.1f    %.1f  %.1f  %.1f " %(
        self.crystal_symmetry.unit_cell().parameters())

  def lower_upper_bounds(self):
    lower_bounds=self.origin
    upper_bounds=[]
    for a,b in zip(self.origin,self.all):
      upper_bounds.append(a+b)
    return list(self.origin),list(upper_bounds)

class info_object:
  def __init__(self,
      ncs_obj=None,
      min_b=None,
      max_b=None,
      ncs_group_list=None,
      origin_shift=None,
      crystal_symmetry=None, # after density_select
      original_crystal_symmetry=None, # before density_select
      edited_volume_list=None,
      region_range_dict=None,
      selected_regions=None,
      ncs_related_regions=None,
      self_and_ncs_related_regions=None,
      map_files_written=None,
      bad_region_list=None,
      region_centroid_dict=None,
      original_id_from_id=None,
      remainder_id_dict=None,  # dict relating regions in a remainder object to
      params=None, # input params
      input_pdb_info=None,
      input_map_info=None,
      input_ncs_info=None,
      input_seq_info=None,
      shifted_pdb_info=None,
      shifted_map_info=None,
      shifted_ncs_info=None,
      shifted_used_ncs_info=None,
      n_residues=None,
      solvent_fraction=None,
      output_ncs_au_map_info=None,
      output_ncs_au_mask_info=None,
      output_ncs_au_pdb_info=None,
      output_box_map_info=None,
      output_box_mask_info=None,
      output_region_map_info_list=None,
      output_region_pdb_info_list=None,
      sharpening_info_obj=None,
    ):
    if not selected_regions: selected_regions=[]
    if not ncs_related_regions: ncs_related_regions=[]
    if not self_and_ncs_related_regions: self_and_ncs_related_regions=[]
    if not map_files_written: map_files_written=[]
    if not output_region_map_info_list: output_region_map_info_list=[]
    if not output_region_pdb_info_list: output_region_pdb_info_list=[]
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())

    self.object_type="segmentation_info"
    import time
    self.init_asctime=time.asctime()

  def is_segmentation_info_object(self):
    return True

  def set_params(self,params):
    self.params=deepcopy(params)

  def set_input_seq_info(self,file_name=None,n_residues=None):
    self.input_seq_info=seq_info_object(file_name=file_name,
       n_residues=n_residues)

  def set_input_pdb_info(self,file_name=None,n_residues=None):
    self.input_pdb_info=pdb_info_object(file_name=file_name,
     n_residues=n_residues)

  def set_input_ncs_info(self,file_name=None,number_of_operators=None):
    self.input_ncs_info=ncs_info_object(file_name=file_name,
      number_of_operators=number_of_operators)

  def update_ncs_info(self,number_of_operators=None,is_helical_symmetry=None,
      shifted=False):
    if shifted:
      ncs_info=self.shifted_ncs_info
    else:
      ncs_info=self.input_ncs_info
    assert ncs_info
    if number_of_operators is not None:
      ncs_info.update_number_of_operators(
        number_of_operators=number_of_operators)
    if is_helical_symmetry is not None:
      ncs_info.update_is_helical_symmetry(
        is_helical_symmetry=is_helical_symmetry)

  def set_sharpening_info(self,sharpening_info_obj=None):
     self.sharpening_info_obj=sharpening_info_obj

  def set_input_map_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None):
    self.input_map_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      is_map=True)

  def set_ncs_obj(self,ncs_obj=None):
    self.ncs_obj=ncs_obj

  def set_origin_shift(self,origin_shift=None):
    if not origin_shift: origin_shift=(0,0,0)
    self.origin_shift=tuple(origin_shift)

  def set_crystal_symmetry(self,crystal_symmetry):
    self.crystal_symmetry=deepcopy(crystal_symmetry)

  def set_original_crystal_symmetry(self,crystal_symmetry):
    self.original_crystal_symmetry=deepcopy(crystal_symmetry)

  def set_shifted_map_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None,b_sharpen=None):
    self.shifted_map_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      b_sharpen=b_sharpen,
      is_map=True)

  def set_shifted_pdb_info(self,file_name=None,n_residues=None):
    self.shifted_pdb_info=pdb_info_object(file_name=file_name,
     n_residues=n_residues)

  def set_shifted_ncs_info(self,file_name=None,number_of_operators=None,
       is_helical_symmetry=None):
    self.shifted_ncs_info=ncs_info_object(file_name=file_name,
      number_of_operators=number_of_operators,
      is_helical_symmetry=is_helical_symmetry)

  def set_shifted_used_ncs_info(self,file_name=None,number_of_operators=None,
       is_helical_symmetry=None):
    self.shifted_used_ncs_info=ncs_info_object(file_name=file_name,
      number_of_operators=number_of_operators,
      is_helical_symmetry=is_helical_symmetry)

  def set_solvent_fraction(self,solvent_fraction):
    self.solvent_fraction=solvent_fraction

  def set_n_residues(self,n_residues): # may not be the same as seq file
    self.n_residues=n_residues

  def set_output_ncs_au_map_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None):
    self.output_ncs_au_map_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      is_map=True)

  def set_output_ncs_au_mask_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None):
    self.output_ncs_au_mask_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      is_map=False)

  def set_output_ncs_au_pdb_info(self,file_name=None,n_residues=None):
    self.output_ncs_au_pdb_info=pdb_info_object(file_name=file_name,
     n_residues=n_residues)

  def set_output_box_map_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None):
    self.output_box_map_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      is_map=True)

  def set_output_box_mask_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None):
    self.output_box_mask_info=map_info_object(file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      is_map=False)

  def add_output_region_map_info(self,file_name=None,crystal_symmetry=None,
    origin=None,all=None,map_id=None):
    self.output_region_map_info_list.append(map_info_object(
      file_name=file_name,
      crystal_symmetry=crystal_symmetry,
      origin=origin,
      all=all,
      id=len(self.output_region_map_info_list)+1,
      map_id=map_id,
      is_map=True)
     )

  def add_output_region_pdb_info(self,file_name=None,n_residues=None):
    self.output_region_pdb_info_list.append(pdb_info_object(
      file_name=file_name,
      n_residues=n_residues)
     )


  def show_summary(self,out=sys.stdout):
    print >>out,"\n==========  Summary of %s: ========\n" %(self.object_type)
    print >>out,"Created: %s" %(self.init_asctime)
    print >>out,"\nInput files used:\n"
    if self.input_map_info:
      self.input_map_info.show_summary(out=out)
    if self.input_pdb_info:
      self.input_pdb_info.show_summary(out=out)
    if self.input_ncs_info:
      self.input_ncs_info.show_summary(out=out)
    if self.input_seq_info:
      self.input_seq_info.show_summary(out=out)

    print >>out

    if self.crystal_symmetry:
      print >>out,"Working unit cell: %.1f  %.1f  %.1f    %.1f  %.1f  %.1f " %(
        self.crystal_symmetry.unit_cell().parameters())

    if self.n_residues:
      print >>out,"Estimated total number of residues: %d" %(self.n_residues)

    if self.solvent_fraction:
      print >>out,"Estimated solvent fraction: %5.3f" %(self.solvent_fraction)

    if self.origin_shift and self.origin_shift != (0,0,0):
      print >>out,\
      "\nOrigin offset applied: %.1f  %.1f  %.1f" %(self.origin_shift)
    else:
      print >>out,"\nNo origin offset applied"

    if self.shifted_map_info:
      print >>out,"\nShifted/sharpened map, pdb and ncs files created "+\
         "(after origin offset):\n"
      if self.shifted_map_info:
        self.shifted_map_info.show_summary(out=out)
      if self.shifted_pdb_info:
        self.shifted_pdb_info.show_summary(out=out)
      if self.shifted_ncs_info:
        self.shifted_ncs_info.show_summary(out=out)

    if self.output_ncs_au_pdb_info:
      print >>out,"\nOutput PDB file with dummy atoms representing the NCS AU:"
      self.output_ncs_au_pdb_info.show_summary(out=out)

    if self.output_ncs_au_mask_info or self.output_ncs_au_map_info:
      print >>out,"\nOutput map files showing just the NCS AU (same size",
      if self.origin_shift and self.origin_shift != (0,0,0):
        print >>out,"\nand location as shifted map files:\n"
      else:
        print >>out,"\nand location as input map:\n"

      if self.output_ncs_au_mask_info:
        self.output_ncs_au_mask_info.show_summary(out=out)
      if self.output_ncs_au_map_info:
        self.output_ncs_au_map_info.show_summary(out=out)

    if self.output_box_mask_info or self.output_box_map_info:
      print >>out,"\nOutput cut-out map files trimmed to contain just "+\
        "the \nNCS AU (superimposed on",
      if self.origin_shift and self.origin_shift != (0,0,0):
        print >>out,"shifted map files, note origin offset):\n"
      else:
        print >>out,"input map, note origin offset):\n"

      if self.output_box_mask_info:
        self.output_box_mask_info.show_summary(out=out)
      if self.output_box_map_info:
        self.output_box_map_info.show_summary(out=out)

    if self.output_region_pdb_info_list:
      print >>out,"\nOutput PDB files representing one region of connected"+\
        " density.\nThese are useful for marking where to look in cut-out map"+\
        " files."
      for output_region_pdb_info in self.output_region_pdb_info_list:
        output_region_pdb_info.show_summary(out=out)

    if self.output_region_map_info_list:
      print >>out,"\nOutput cut-out map files trimmed to contain just "+\
        "one region of \nconnected density (superimposed on",
      if self.origin_shift and self.origin_shift != (0,0,0):
        print >>out,"shifted map files, note origin offset):\n"
      else:
        print >>out," input map, note origin offset):\n"
      for output_region_map_info in self.output_region_map_info_list:
        output_region_map_info.show_summary(out=out)

    print >>out,"\n"+50*"="+"\n"

class make_ccp4_map: # just a holder so map_to_structure_factors will run
  def __init__(self,map=None,unit_cell=None):
    self.data=map
    self.unit_cell_parameters=unit_cell.parameters()
    self.space_group_number=1

class b_vs_region_info:
  def __init__(self):
    self.b_iso=0.
    self.b_vs_region_dict={}
    self.sa_sum_v_vs_region_dict={}
    self.sa_nn_vs_region_dict={}
    self.sa_ratio_b_vs_region_dict={}

class box_sharpening_info:
  def __init__(self,tracking_data=None,
      crystal_symmetry=None,
      solvent_fraction=None,
      wrapping=None,
      n_real=None):
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    del self.tracking_data # do not save it
    if tracking_data:
      self.crystal_symmetry=tracking_data.crystal_symmetry
      self.solvent_fraction=tracking_data.solvent_fraction
      self.wrapping=tracking_data.params.crystal_info.use_sg_symmetry

class sharpening_info:
  def __init__(self,
      tracking_data=None,
      crystal_symmetry=None,
      is_crystal=None,
      sharpening_method=None,
      solvent_fraction=None,
      n_residues=None,
      ncs_copies=None,
      ncs_file=None,
      seq_file=None,
      n_real=None,
      region_weight=None,
      n_bins=None,
      eps=None,
      d_min=None,
      d_min_ratio=None,
      rmsd=None,
      k_sol=None,
      b_sol=None,
      fraction_complete=None,
      wrapping=None,
      sharpening_target=None,
      residual_target=None,
      fraction_occupied=None,
      resolution=None, # changed from d_cut
      resolution_dependent_b=None,  # linear sharpening
      b_sharpen=None,
      b_iso=None,  # expected B_iso after applying b_sharpen
      k_sharpen=None,
      kurtosis=None,
      adjusted_sa=None,
      sa_ratio=None,
      normalized_regions=None,
      score=None,
      input_weight_map_pickle_file=None,
      output_weight_map_pickle_file=None,
      read_sharpened_maps=None,
      write_sharpened_maps=None,
      select_sharpened_map=None,
      output_directory=None,
      smoothing_radius=None,
      local_sharpening=None,
      local_aniso_in_local_sharpening=None,
      use_local_aniso=None,
      original_aniso_obj=None,
      auto_sharpen=None,
      box_in_auto_sharpen=None,
      use_weak_density=None,
      discard_if_worse=None,
      max_box_fraction=None,
      mask_atoms=None,
      mask_atoms_atom_radius=None,
      value_outside_atoms=None,
      soft_mask=None,
      search_b_min=None,
      search_b_max=None,
      search_b_n=None,
      maximum_low_b_adjusted_sa=None,
      box_sharpening_info_obj=None,
      chain_type=None,
      target_scale_factors=None,
      remove_aniso=None,
      d_min_list=None,
      verbose=None,
      pdb_inp=None,  # XXX probably do not need this
        ):

    from libtbx import adopt_init_args
    adopt_init_args(self, locals())
    del self.tracking_data  # don't need it as part of the object
    del self.box_sharpening_info_obj# don't need it as part of the object
    del self.pdb_inp # don't need it as part of the object

    if tracking_data:  # use tracking data information
      self.update_with_tracking_data(tracking_data=tracking_data)

    if box_sharpening_info_obj: # update information
      self.update_with_box_sharpening_info(
         box_sharpening_info_obj=box_sharpening_info_obj)

    if self.resolution_dependent_b is None:
      self.resolution_dependent_b=[0,0,0]

    if self.target_scale_factors and \
        self.sharpening_method!='model_sharpening' \
        and self.sharpening_method!='half_map_sharpening':
      assert self.sharpening_method is None # XXX may want to print out error
      self.sharpening_method='model_sharpening'

    if self.sharpening_method=='b_iso' and self.k_sharpen is not None:
      self.k_sharpen=None

    if pdb_inp:
        self.sharpening_method='model_sharpening'
        self.box_in_auto_sharpen=True
        self.sharpening_target='model'
   
  def set_resolution_dependent_b(self,
    resolution_dependent_b=None,
    sharpening_method='resolution_dependent'):
    if resolution_dependent_b:
      self.resolution_dependent_b=resolution_dependent_b
    if sharpening_method:
      self.sharpening_method=sharpening_method

  def sharpening_is_defined(self):
    if self.sharpening_method is None:
      return False

    if self.target_scale_factors:
      return True

    if self.b_iso is not None or \
       self.b_sharpen is not None or \
       (self.resolution_dependent_b is not None and
        self.resolution_dependent_b!=[0,0,0]):
      return True

    return False

  def update_with_box_sharpening_info(self,box_sharpening_info_obj=None):
      if not box_sharpening_info_obj:
        return self
      self.crystal_symmetry=box_sharpening_info_obj.crystal_symmetry
      self.solvent_fraction=box_sharpening_info_obj.solvent_fraction
      self.wrapping=box_sharpening_info_obj.wrapping
      self.n_real=box_sharpening_info_obj.n_real
      return self

  def update_with_tracking_data(self,tracking_data=None):
      self.update_with_params(params=tracking_data.params,
         crystal_symmetry=tracking_data.crystal_symmetry,
         solvent_fraction=tracking_data.solvent_fraction,
         n_residues=tracking_data.n_residues,
         ncs_copies=tracking_data.input_ncs_info.number_of_operators)
      return self

  def update_with_params(self,params=None,
     crystal_symmetry=None,
     is_crystal=None,
     solvent_fraction=None,
     auto_sharpen=None,
     sharpening_method=None,
     pdb_inp=None,
     half_map_data_list=None,
     n_residues=None,ncs_copies=None):
      self.crystal_symmetry=crystal_symmetry
      self.is_crystal=is_crystal
      self.solvent_fraction=solvent_fraction
      self.auto_sharpen=auto_sharpen
      self.n_residues=n_residues
      self.ncs_copies=ncs_copies
      self.seq_file=params.input_files.seq_file
      self.chain_type=params.crystal_info.chain_type
      self.verbose=params.control.verbose

      self.wrapping=params.crystal_info.use_sg_symmetry
      self.fraction_occupied=params.map_modification.fraction_occupied
      self.sa_percent=params.map_modification.sa_percent
      self.region_weight=params.map_modification.region_weight
      self.max_regions_to_test=params.map_modification.max_regions_to_test
      self.d_min_ratio=params.map_modification.d_min_ratio
      self.rmsd=params.map_modification.rmsd
      self.k_sol=params.map_modification.k_sol
      self.b_sol=params.map_modification.b_sol
      self.fraction_complete=params.map_modification.fraction_complete
      self.resolution=params.crystal_info.resolution  # changed from d_cut
      #  NOTE:
      #  resolution=X-ray resolution or nominal resolution of cryoEM map
      #  high-res cutoff of reflections is d_min*d_min_ratio

      self.max_box_fraction=params.map_modification.max_box_fraction
      self.mask_atoms=params.map_modification.mask_atoms
      self.mask_atoms_atom_radius=params.map_modification.mask_atoms_atom_radius
      self.value_outside_atoms=params.map_modification.value_outside_atoms
      self.soft_mask=params.map_modification.soft_mask
      self.k_sharpen=params.map_modification.k_sharpen
      self.sharpening_target=params.map_modification.sharpening_target
      self.residual_target=params.map_modification.residual_target
      self.eps=params.map_modification.eps
      self.n_bins=params.map_modification.n_bins
      self.input_weight_map_pickle_file=params.input_files.input_weight_map_pickle_file
      self.output_weight_map_pickle_file=params.output_files.output_weight_map_pickle_file
      self.read_sharpened_maps=params.map_modification.read_sharpened_maps
      self.write_sharpened_maps=params.map_modification.write_sharpened_maps
      self.select_sharpened_map=params.map_modification.select_sharpened_map
      self.output_directory=params.output_files.output_directory
      self.smoothing_radius=params.map_modification.smoothing_radius
      self.local_sharpening=params.map_modification.local_sharpening
      self.local_aniso_in_local_sharpening=\
         params.map_modification.local_aniso_in_local_sharpening
      self.box_in_auto_sharpen=params.map_modification.box_in_auto_sharpen
      self.use_weak_density=params.map_modification.use_weak_density
      self.discard_if_worse=params.map_modification.discard_if_worse
      self.box_center=params.map_modification.box_center
      self.box_size=params.map_modification.box_size
      self.remove_aniso=params.map_modification.remove_aniso
      self.min_ratio_of_ncs_copy_to_first=\
         params.segmentation.min_ratio_of_ncs_copy_to_first
      self.max_ratio_to_target=params.segmentation.max_ratio_to_target
      self.min_ratio_to_target=params.segmentation.min_ratio_to_target
      self.residues_per_region=params.segmentation.residues_per_region
      self.starting_density_threshold=\
         params.segmentation.starting_density_threshold
      self.density_threshold=params.segmentation.density_threshold
      self.min_ratio=params.segmentation.min_ratio
      self.min_volume=params.segmentation.min_volume
      self.search_b_min=params.map_modification.search_b_min
      self.search_b_max=params.map_modification.search_b_max
      self.search_b_n=params.map_modification.search_b_n
      self.maximum_low_b_adjusted_sa=\
         params.map_modification.maximum_low_b_adjusted_sa

      if sharpening_method is not None:
        self.sharpening_method=sharpening_method

      if not self.sharpening_method and \
         len(params.map_modification.auto_sharpen_methods)==1:
        self.sharpening_method=params.map_modification.auto_sharpen_methods[0]

      if half_map_data_list or self.sharpening_method=='half_map_sharpening':
        self.sharpening_method='half_map_sharpening'
        self.sharpening_target='half_map'

      elif pdb_inp or self.sharpening_method=='model_sharpening':
        self.sharpening_method='model_sharpening'
        self.box_in_auto_sharpen=True
        self.sharpening_target='model'

      elif params.map_modification.b_iso is not None or \
          params.map_modification.b_sharpen is not None:
        if self.sharpening_method is None: 
          raise Sorry("b_iso is not set")
        # if sharpening values are specified, set them
        if params.map_modification.b_iso is not None:
          self.b_iso=params.map_modification.b_iso # but we need b_sharpen
        elif params.map_modification.b_sharpen is not None:
          self.b_sharpen=params.map_modification.b_sharpen
      elif (params.map_modification.resolution_dependent_b is not None
        and params.map_modification.resolution_dependent_b!=[0,0,0]):
        self.sharpening_method='resolution_dependent'
        self.resolution_dependent_b=\
            params.map_modification.resolution_dependent_b

      if self.sharpening_method=='b_iso' and self.k_sharpen is not None:
        self.k_sharpen=None
      return self
  def show_summary(self,verbose=False,out=sys.stdout):
    method_summary_dict={
       'b_iso':"Overall b_iso sharpening",
       'b_iso_to_d_cut':"b_iso sharpening to high_resolution cutoff",
       'resolution_dependent':"Resolution-dependent sharpening",
       'model_sharpening':"Model sharpening",
       'half_map_sharpening':"Half-map sharpening",
       'no_sharpening':"No sharpening",
       None:"No sharpening",
        }

    target_summary_dict={
       'adjusted_sa':"Adjusted surface area",
       'kurtosis':"Map kurtosis",
       'model':"Map-model CC",
      }
    print >>out,"\nSummary of sharpening:\n"

    print >>out,"Sharpening method used:         %s\n" %(
       method_summary_dict.get(self.sharpening_method))

    if self.sharpening_method=="b_iso":
      if self.b_sharpen is not None:
        print >>out,"Overall b_sharpen applied:      %7.2f A**2" %(
          self.b_sharpen)
      if self.b_iso is not None:
        print >>out,"Final b_iso obtained:           %7.2f A**2" %(self.b_iso)
    elif self.sharpening_method=="b_iso_to_d_cut":
      if self.b_sharpen is not None:
        print >>out,"Overall b_sharpen applied:      %7.2f A**2" %(
          self.b_sharpen)
      print >>out,"High-resolution cutoff:         %7.2f A" %(self.resolution)
    elif self.sharpening_method=="resolution_dependent":
      print >>out,"Resolution-dependent b values (%7.2f,%7.2f,%7.2f)\n" %(
        tuple(self.resolution_dependent_b))

      print >>out,"Effective b_iso vs resolution obtained:"
      from cctbx.maptbx.refine_sharpening import get_effective_b_values
      d_min_values,b_values=get_effective_b_values(
        d_min_ratio=self.d_min_ratio,
         resolution_dependent_b=self.resolution_dependent_b,
         resolution=self.resolution)
      print >>out,"                                Resolution  Effective B-iso"
      print >>out,"                                    (A)         (A**2)"
      for dd,b in zip(d_min_values,b_values):
        print >>out,"                                 %7.1f       %7.2f " %(
         dd,b)

    elif self.sharpening_method=="model_sharpening":
      print >>out,"Resolution-dependent model sharpening"
      print >>out,"Scale vs resolution:"
      for d_min,sc in zip(
        self.d_min_list,
        self.target_scale_factors):
        print >>out,"Dmin: %7.2f  Scale: %7.2f" %(d_min,sc)

    elif self.sharpening_method=="half_map_sharpening":
      print >>out,"Resolution-dependent half-map sharpening"
      if self.d_min_list and self.target_scale_factors:
        print >>out,"Scale vs resolution:"
        for d_min,sc in zip(
          self.d_min_list,
          self.target_scale_factors):
          print >>out,"Dmin: %7.2f  Scale: %7.2f" %(d_min,sc)

    if self.sharpening_method in ["b_iso_to_d_cut"] and \
      self.k_sharpen and self.resolution:
        print >>out,"Transition from sharpening"
        print >>out,"   to not sharpening (k_sharpen):%7.2f " %(self.k_sharpen)

    print >>out,"\nSharpening target used:         %s" %(
       target_summary_dict.get(self.sharpening_target))
    if self.adjusted_sa is not None:
      print >>out,"Final adjusted map surface area:  %7.2f" %(self.adjusted_sa)
    if self.kurtosis is not None:
      print >>out,"Final map kurtosis:               %7.2f" %(self.kurtosis)

    print >>out

    if verbose:
      for x in dir(self):
        if x.startswith("__"): continue
        if type(getattr(self,x)) in [type('a'),type(1),type(1.),type([]),
          type((1,2,))]:
          print >>out,"%s : %s" %(x,getattr(self,x))

  def get_effective_b_iso(self,map_data=None,out=sys.stdout):
    map_coeffs_ra,map_coeffs,f_array,phases=effective_b_iso(map_data=map_data,
      resolution=self.resolution,
      d_min_ratio=self.d_min_ratio,
      crystal_symmetry=self.crystal_symmetry,
       out=out)
    return map_coeffs_ra.b_iso

  def sharpen_and_score_map(self,map_data=None,out=sys.stdout):
    if self.n_real is None: # need to get it
      self.n_real=map_data.all()
    #print >>out,"B-iso before sharpening:",
    self.get_effective_b_iso(map_data=map_data,out=out)
    self.map_data=sharpen_map_with_si(
      sharpening_info_obj=self,map_data=map_data,
        resolution=self.resolution,out=out)
    #print >>out,"B-iso after sharpening:",
    self.get_effective_b_iso(map_data=self.map_data,out=out)
    score_map(map_data=self.map_data,
        sharpening_info_obj=self,
        out=null_out())
    return self

  def show_score(self,out=sys.stdout):
    print >>out,\
       "Adjusted surface area: %7.3f  Kurtosis: %7.3f  Score: %7.3f\n" %(
       self.adjusted_sa,self.kurtosis,self.score)

  def is_resolution_dependent_sharpening(self):
    if self.sharpening_method=='resolution_dependent':
       return True
    else:
       return False

  def is_model_sharpening(self):
    if self.sharpening_method=='model_sharpening':
       return True
    else:
       return False

  def is_half_map_sharpening(self):
    if self.sharpening_method=='half_map_sharpening':
       return True
    else:
       return False

  def as_map_coeffs(self,out=sys.stdout):
    map_data=getattr(self,'map_data',None)
    if map_data:
      map_coeffs,dummy=get_f_phases_from_map(map_data=self.map_data,
       crystal_symmetry=self.crystal_symmetry,
       d_min=self.resolution,
       d_min_ratio=self.d_min_ratio,
       return_as_map_coeffs=True,
       out=out)
      return map_coeffs
    else:
      return None

  def as_map_data(self):
    return getattr(self,'map_data',None)


class ncs_group_object:
  def __init__(self,
      ncs_obj=None,
      ncs_ops_used=None,
      ncs_group_list=None,
      edited_mask=None,
      crystal_symmetry=None,
      max_cell_dim=None,
      origin_shift=None,
      edited_volume_list=None,
      region_range_dict=None,
      selected_regions=None,
      ncs_related_regions=None,
      self_and_ncs_related_regions=None,
      equiv_dict=None,
      map_files_written=None,
      bad_region_list=None,
      region_centroid_dict=None,
      region_scattered_points_dict=None,
      shared_group_dict=None,
      co=None,
      min_b=None,
      max_b=None,
      original_id_from_id=None,
      remainder_id_dict=None,  # dict relating regions in a remainder object to
                               #  those in the original map
         ):
    if not selected_regions: selected_regions=[]
    if not ncs_related_regions: ncs_related_regions=[]
    if not self_and_ncs_related_regions: self_and_ncs_related_regions=[]
    if not map_files_written: map_files_written=[]
    from libtbx import adopt_init_args
    adopt_init_args(self, locals())

    if self.crystal_symmetry and not self.max_cell_dim:
      self.max_cell_dim=0.
      for x in self.crystal_symmetry.unit_cell().parameters()[:3]:
        self.max_cell_dim=max(max_cell_dim,x)

  def as_info_object(self):
    return info_object(
      ncs_obj=self.ncs_obj,
      max_b=self.max_b,
      min_b=self.min_b,
      ncs_group_list=self.ncs_group_list,
      origin_shift=self.origin_shift,
      edited_volume_list=self.edited_volume_list,
      region_range_dict=self.region_range_dict,
      selected_regions=self.selected_regions,
      ncs_related_regions=self.ncs_related_regions,
      self_and_ncs_related_regions=self.self_and_ncs_related_regions,
      bad_region_list=self.bad_region_list,
      region_centroid_dict=self.region_centroid_dict,
      original_id_from_id=self.original_id_from_id,
      map_files_written=self.map_files_written,
     )

  def set_ncs_ops_used(self,ncs_ops_used):
    self.ncs_ops_used=deepcopy(ncs_ops_used)

  def set_selected_regions(self,selected_regions):
    self.selected_regions=deepcopy(selected_regions)

  def set_ncs_related_regions(self,ncs_related_regions):
    self.ncs_related_regions=deepcopy(ncs_related_regions)

  def set_self_and_ncs_related_regions(self,self_and_ncs_related_regions):
    self.self_and_ncs_related_regions=deepcopy(self_and_ncs_related_regions)

  def set_map_files_written(self,map_files_written):
    self.map_files_written=deepcopy(map_files_written)

def scale_map(map,scale_rms=1.0,out=sys.stdout):
    sd=map.as_double().as_1d().sample_standard_deviation()
    if (sd > 1.e-10):
      scale=scale_rms/sd
      if 0: print >>out,"Scaling map by %7.3f to set SD=1" %(scale)
      map=map*scale
    return map

def scale_map_coeffs(map_coeffs,scale_max=100000.,out=sys.stdout):
  f_array,phases=map_coeffs_as_fp_phi(map_coeffs)
  max_value=f_array.data().min_max_mean().max
  scale=scale_max/max(1.e-10,max_value)
  if 0:
    print >>out,"Scaling map_coeffs by %9.3f to yield maximum of %7.0f" %(
     scale,scale_max)
  return f_array.array(data=f_array.data()*scale
       ).phase_transfer(phase_source=phases, deg=True)
  

def get_map_object(file_name=None,out=sys.stdout):
  # read a ccp4 map file and return sg,cell and map objects 2012-01-16
  from iotbx import ccp4_map
  m = ccp4_map.map_reader(file_name=file_name)
  print >>out,"MIN MAX MEAN RMS of map: %7.2f %7.2f  %7.2f  %7.2f " %(
      m.header_min, m.header_max, m.header_mean, m.header_rms)
  print >>out,"grid: ",m.unit_cell_grid
  print >>out,"cell:  %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f  " %tuple(
     m.unit_cell_parameters)
  print >>out,"SG: ",m.space_group_number
  print >>out,"ORIGIN: ",m.data.origin()
  print >>out,"EXTENT: ",m.data.all()
  print >>out,"IS PADDED: ",m.data.is_padded()

  map_data=m.data
  acc=map_data.accessor()
  shift_needed = not \
     (map_data.focus_size_1d() > 0 and map_data.nd() == 3 and
      map_data.is_0_based())
  if(shift_needed):
    map_data = map_data.shift_origin()
    origin_shift=(
      m.data.origin()[0]/m.data.all()[0],
      m.data.origin()[1]/m.data.all()[1],
      m.data.origin()[2]/m.data.all()[2])
    origin_frac=origin_shift
  else:
    origin_frac=(0.,0.,0.)

  offsets=[]
  need_offset=False
  for o,g,e in zip(map_data.origin(),m.unit_cell_grid,map_data.all() ):
    if o != 0:
      raise Sorry("Sorry the origin of CCP4 style maps must be (0,0,0).\n"+
        " The file %s has the origin of %s" %(file_name,str(map_data.origin())))
    offset=e-g
    if offset < 0 or offset > 1:
      raise Sorry("Sorry the extent of CCP4 style maps must be the same as "+
       "the grid or 1 grid point larger than the grid.  "+
       "The file %s has a grid of %s and extent of %s" %(
       file_name,str(m.unit_cell_grid),str(map_data.all())))
    if offset: need_offset=True
    offsets.append(offset)
  if need_offset:
    if offsets != [1,1,1]:
      raise Sorry("Sorry the extent of CCP4 style maps must be the same or "+
       "one more \nthan the grid, and all must be the same or all one more.  "+
       "\nThe file %s has a grid of %s and extent of %s" %(
       file_name,str(m.unit_cell_grid),str(map_data.all())))
    if origin_frac!=(0.,0.,0.):  # this was a shifted map...we can't do this
      raise Sorry("Sorry if a CCP4 map has an origin other than (0,0,0) "+
        "the extent \nof the map must be the same as the grid for "+
        "segment_and_split_map routines."+
       "The file %s has a grid of %s and extent of %s" %(
       file_name,str(m.unit_cell_grid),str(map_data.all())))
    if offset: need_offset=True
    map=map_data[:-1,:-1,:-1]
    acc=map.accessor()
  else:
    map=map_data

  # now get space group and cell
  from cctbx import crystal
  from cctbx import sgtbx
  from cctbx import uctbx
  if m.space_group_number==0:
    n=1 # fix mrc formatting
  else:
    n=m.space_group_number
  space_group_info=sgtbx.space_group_info(number=n)
  unit_cell=uctbx.unit_cell(m.unit_cell_parameters)
  crystal_symmetry=crystal.symmetry(
    unit_cell=unit_cell,space_group_info=space_group_info)
  print >>out, "\nCrystal symmetry used: "
  crystal_symmetry.show_summary(f=out)
  space_group=crystal_symmetry.space_group()

  map=scale_map(map,out=out)

  return map,space_group,unit_cell,crystal_symmetry,origin_frac,acc

def write_ccp4_map(crystal_symmetry, file_name, map_data):
  iotbx.ccp4_map.write_ccp4_map(
      file_name=file_name,
      unit_cell=crystal_symmetry.unit_cell(),
      space_group=crystal_symmetry.space_group(),
      map_data=map_data.as_double(),
      labels=flex.std_string([""]))

def set_up_xrs(crystal_symmetry=None):  # dummy xrs to write out atoms

  lines=["ATOM     92  SG  CYS A  10       8.470  28.863  18.423  1.00 22.05           S"] # just a random line to set up x-ray structure
  from cctbx.array_family import flex
  from cctbx import xray
  pdb_inp=iotbx.pdb.input(source_info="",lines=lines)
  xrs = pdb_inp.xray_structure_simple(crystal_symmetry=crystal_symmetry)
  scatterers = flex.xray_scatterer()
  return xrs,scatterers

def write_atoms(tracking_data=None,sites=None,file_name=None,
      crystal_symmetry=None,out=sys.stdout):
    if crystal_symmetry is None:
       crystal_symmetry=tracking_data.crystal_symmetry
    xrs,scatterers=set_up_xrs(crystal_symmetry=crystal_symmetry)
    from cctbx import xray
    unit_cell=crystal_symmetry.unit_cell()
    for xyz_cart in sites:
      scatterers.append( xray.scatterer(scattering_type="O", label="O",
        site=unit_cell.fractionalize(xyz_cart), u=0.38, occupancy=1.0))
    write_xrs(xrs=xrs,scatterers=scatterers,file_name=file_name,out=out)


def write_xrs(xrs=None,scatterers=None,file_name="atoms.pdb",out=sys.stdout):
  from cctbx import xray
  xrs = xray.structure(xrs, scatterers=scatterers)
  text=xrs.as_pdb_file()
  f=open(file_name,'w')
  print >>f,text
  f.close()
  print >>out,"Atoms written to %s" %file_name

def get_b_iso(miller_array,d_min=None,return_aniso_scale_and_b=False):

  if d_min:
    res_cut_array=miller_array.resolution_filter(d_max=None,
       d_min=d_min)
  else:
    res_cut_array=miller_array

  from mmtbx.scaling import absolute_scaling
  try:
    aniso_scale_and_b=absolute_scaling.ml_aniso_absolute_scaling(
      miller_array=res_cut_array, n_residues=200, n_bases=0)
    b_cart=aniso_scale_and_b.b_cart
  except Exception,e:
    b_cart=[0,0,0]
    aniso_scale_and_b=None
  b_aniso_mean=0.
  if b_cart:
    for k in [0,1,2]:
      b_aniso_mean+=b_cart[k]
  if return_aniso_scale_and_b:
    return b_aniso_mean/3.0,aniso_scale_and_b
  else: # usual
    return b_aniso_mean/3.0

def map_coeffs_as_fp_phi(map_coeffs):
  amplitudes=map_coeffs.amplitudes()
  amplitudes.set_observation_type_xray_amplitude()
  assert amplitudes.is_real_array()
  phases=map_coeffs.phases(deg=True)
  return amplitudes,phases

def map_coeffs_to_fp(map_coeffs):
  amplitudes=map_coeffs.amplitudes()
  amplitudes.set_observation_type_xray_amplitude()
  assert amplitudes.is_real_array()
  return amplitudes

def get_f_phases_from_model(f_array=None,pdb_inp=None,overall_b=None,
     k_sol=None, b_sol=None, out=sys.stdout):
  xray_structure=pdb_inp.construct_hierarchy().extract_xray_structure(
     crystal_symmetry=f_array.crystal_symmetry())

  model_f_array=f_array.structure_factors_from_scatterers(
      xray_structure = xray_structure).f_calc()

  return model_f_array

def get_f_phases_from_map(map_data=None,crystal_symmetry=None,d_min=None,
      d_min_ratio=None,return_as_map_coeffs=False,remove_aniso=None,
        out=sys.stdout):
    from mmtbx.command_line.map_to_structure_factors import run as map_to_sf
    if d_min and d_min_ratio is not None:
      d_min_ratio_use=d_min_ratio
      map_coeffs=None
      n_try=0
      max_try=5
      while d_min_ratio_use <= 1 and n_try<=max_try:
        n_try+=1
        args=['d_min=%s' %(d_min*d_min_ratio_use)]
        try:
          map_coeffs=map_to_sf(args=args,
            space_group_number=crystal_symmetry.space_group().type().number(),
            ccp4_map=make_ccp4_map(map_data,crystal_symmetry.unit_cell()),
            return_as_miller_arrays=True,nohl=True,out=null_out())
        except Exception, e:
          if str(e).find("Too high resolution")> -1:
            d_min_ratio_use=d_min_ratio_use**0.5 # move towards 1
            continue
          else:
            raise Sorry("Failed to run map_to_structure_factors.\n "+
              "Msg: %s" %(str(e)))
        break  # it was ok

      if not map_coeffs:
            raise Sorry("Failed to run map_to_structure_factors (no map coeffs)...")

    elif d_min:
       args=['d_min=%s' %(d_min)]
       print >>out,"Using all grid points for inversion"
    else:
       args=['d_min=None','box=True']
       print >>out,"Using all grid points for inversion"
    map_coeffs=map_to_sf(args=args,
         space_group_number=crystal_symmetry.space_group().type().number(),
         ccp4_map=make_ccp4_map(map_data,crystal_symmetry.unit_cell()),
         return_as_miller_arrays=True,nohl=True,out=null_out())

    map_coeffs=scale_map_coeffs(map_coeffs,out=out)

    if remove_aniso:
      print >>out,"\nRemoving aniso in data before analysis\n"

    from cctbx.maptbx.refine_sharpening import analyze_aniso
    map_coeffs,map_coeffs_ra=analyze_aniso(
         remove_aniso=remove_aniso,
         map_coeffs=map_coeffs,resolution=d_min,out=out)

    if return_as_map_coeffs:
      return map_coeffs,map_coeffs_ra
    else:
      return map_coeffs_as_fp_phi(map_coeffs)


def apply_sharpening(map_coeffs=None,
    sharpening_info_obj=None,
    n_real=None,b_sharpen=None,crystal_symmetry=None,
    target_scale_factors=None,
    f_array=None,phases=None,d_min=None,k_sharpen=None,out=sys.stdout):

    if map_coeffs and f_array is None and phases is None:
      f_array,phases=map_coeffs_as_fp_phi(map_coeffs)

    if sharpening_info_obj is not None:
      b_sharpen=sharpening_info_obj.b_sharpen
      k_sharpen=sharpening_info_obj.k_sharpen
      d_min=sharpening_info_obj.resolution# changed from d_cut
      n_real=sharpening_info_obj.n_real
      target_scale_factors=sharpening_info_obj.target_scale_factors
      n_bins=sharpening_info_obj.n_bins
      remove_aniso=sharpening_info_obj.remove_aniso
      resolution=sharpening_info_obj.resolution
    if target_scale_factors:
      assert sharpening_info_obj is not None
      print >>out,"\nApplying target scale factors vs resolution"
      if not map_coeffs:
        map_coeffs=f_array.phase_transfer(phase_source=phases,deg=True)

      f_array,phases=map_coeffs_as_fp_phi(map_coeffs) 
      f_array_b_iso=get_b_iso(f_array,d_min=d_min)
      if not f_array.binner():
        (local_d_max,local_d_min)=f_array.d_max_min()
        f_array.setup_binner(n_bins=n_bins,d_max=local_d_max,d_min=local_d_min)

      from cctbx.maptbx.refine_sharpening import get_scale_factors
      scale_array=get_scale_factors(f_array,
          target_scale_factors=target_scale_factors)
      scaled_f_array=f_array.customized_copy(data=f_array.data()*scale_array)
      scaled_f_array_b_iso=get_b_iso(scaled_f_array,d_min=d_min)
      print >>out,"\nInitial b_iso for "+\
        "local map: %5.1f A**2     After adjustment: %5.1f A**2" %(
        f_array_b_iso,scaled_f_array_b_iso)

      return get_map_from_map_coeffs(map_coeffs=map_coeffs,
        crystal_symmetry=crystal_symmetry,n_real=n_real)

    elif b_sharpen is None or (
        b_sharpen in [0,None] and k_sharpen in [0,None]):
      if not map_coeffs:
        map_coeffs=f_array.phase_transfer(phase_source=phases,deg=True)
      return get_map_from_map_coeffs(map_coeffs=map_coeffs,
        crystal_symmetry=crystal_symmetry,n_real=n_real)

    elif b_sharpen < 0 or k_sharpen<=0 or k_sharpen is None or d_min is None:
      # 2016-08-10 original method: apply b_sharpen to all data
      # Use this if blurring (b_sharpen<0) or if k_sharpen is not set
      from cctbx import adptbx # next lines from xtriage (basic_analysis.py)
      b_cart_aniso_removed=[ b_sharpen, b_sharpen, b_sharpen, 0, 0, 0]
      from mmtbx.scaling import absolute_scaling
      u_star_aniso_removed=adptbx.u_cart_as_u_star(
        f_array.unit_cell(), adptbx.b_as_u( b_cart_aniso_removed  ) )
      f_array_sharpened=absolute_scaling.anisotropic_correction(
        f_array,0.0,u_star_aniso_removed,must_be_greater_than=-0.0001)
    else:

      # Apply sharpening only to data from infinity to d_min, with transition
      # steepness of k_sharpen.
      data_array=f_array.data()
      sthol_array=f_array.sin_theta_over_lambda_sq()
      d_spacings=f_array.d_spacings()
      scale_array=flex.double()
      import math
      for x,(ind,sthol),(ind1,d) in zip(data_array,sthol_array,d_spacings):
        value=min(20.,max(-20.,k_sharpen*(d_min-d)))
        log_scale=b_sharpen*sthol/(1.+math.exp(value))
        scale_array.append(math.exp(log_scale))
      data_array=data_array*scale_array
      f_array_sharpened=f_array.customized_copy(data=data_array)

    actual_b_iso=get_b_iso(f_array_sharpened,d_min=d_min)
    #print  "B-iso after sharpening by b_sharpen=%6.1f is %7.2f\n" %( b_sharpen,actual_b_iso)
    print >>out, "B-iso after sharpening by b_sharpen=%6.1f is %7.2f\n" %(
      b_sharpen,actual_b_iso)
    sharpened_map_coeffs=f_array_sharpened.phase_transfer(
      phase_source=phases,deg=True)

    # And get new map
    return get_map_from_map_coeffs(map_coeffs=sharpened_map_coeffs,
      crystal_symmetry=crystal_symmetry,
       n_real=n_real)

def get_map_from_map_coeffs(map_coeffs=None,crystal_symmetry=None,
     n_real=None):
    from cctbx import maptbx
    from cctbx.maptbx import crystal_gridding
    if n_real:
      cg=crystal_gridding(
        unit_cell=crystal_symmetry.unit_cell(),
        space_group_info=crystal_symmetry.space_group_info(),
        pre_determined_n_real=n_real)
    else:
      cg=None
    fft_map = map_coeffs.fft_map( resolution_factor = 0.25,
       crystal_gridding=cg,
       symmetry_flags=maptbx.use_space_group_symmetry)
    fft_map.apply_sigma_scaling()
    map_data=fft_map.real_map_unpadded()
    return map_data

def find_ncs_center(map_data,crystal_symmetry=None):
  # find center if necessary:
  origin=list(map_data.origin())
  all=list(map_data.all())
  centroid_wx={}
  centroid_w={}
  from cctbx import maptbx
  for ai in [0,1,2]:
    centroid_wx[ai]=0.
    centroid_w[ai]=0.
    for i in xrange(0,all[ai]):
      if ai==0:
        start_tuple=tuple((i,0,0))
        end_tuple=tuple((i,all[1],all[2]))
      elif ai==1:
         start_tuple=tuple((0,i,0))
         end_tuple=tuple((all[0],i,all[2]))
      elif ai==2:
         start_tuple=tuple((0,0,i))
         end_tuple=tuple((all[0],all[1],i))
      new_map_data = maptbx.copy(map_data,
         start_tuple,end_tuple)
      mean_value=max(0.,new_map_data.as_1d().as_double().min_max_mean().mean)
      centroid_wx[ai]+=mean_value*(i-origin[ai])
      centroid_w[ai]+=mean_value
    if centroid_w[ai]>0:
      centroid_wx[ai]=centroid_wx[ai]/centroid_w[ai]
  print "CENTROID OF DENSITY: (%7.2f, %7.2f, %7.2f) (grid units) " %(
    tuple((centroid_wx[0],centroid_wx[1],centroid_wx[2],)))
  xyz_fract=matrix.col((centroid_wx[0]/all[0],centroid_wx[1]/all[1],centroid_wx[2]/all[2],))
  xyz_cart=crystal_symmetry.unit_cell().orthogonalize(xyz_fract)
  print "CENTROID (A): (%7.3f, %7.3f, %7.3f) " %(
    tuple(xyz_cart))
  return xyz_cart

def get_center_of_map(map_data,crystal_symmetry):
  all=list(map_data.all())
  origin=list(map_data.origin())
  sx,sy,sz=[all[0]/2+origin[0],all[1]/2+origin[1],all[2]/2+origin[2]]
  site_fract=matrix.col((sx/all[0],sy/all[1],sz/all[2],))
  return crystal_symmetry.unit_cell().orthogonalize(site_fract)

def get_ncs_from_map(map_data=None,
      map_ncs_center=None,
      ncs_type=None,
      ncs_center=None,
      helical_rot_deg=None,
      helical_trans_z_angstrom=None,
      two_fold_along_x=None,
      op_max=None,
      crystal_symmetry=None,
      optimize_center=None,
      random_points=None,
      n_rescore=None,
      use_center_of_map_as_center=None,
      min_ncs_cc=0.90,
      out=sys.stdout):

  # Purpose: check through standard point groups and helical symmetry to see
  # if map has symmetry. If ncs_type==ANY then take highest symmetry that fits
  # Otherwise limit to the one specified with ncs_type.
  #  Use a library of symmetry matrices.  For helical symmetry generate it
  #  along the z axis.
  # Center of symmetry is as supplied, or center of map or center of density
  #  If center is not supplied and use_center_of_map_as_center, try that
  #  and return None if it fails to achieve a map cc of min_ncs_cc

  if optimize_center is None:
    if ncs_center is None and (not use_center_of_map_as_center):
      optimize_center=True
      print >>out,"Setting optimize_center=True as no ncs_center is supplied"
    else:
      optimize_center=False

  if ncs_center is not None:
    ncs_center=matrix.col(ncs_center)
  elif use_center_of_map_as_center:
    print >>out,"Using center of map as NCS center"
    ncs_center=map_ncs_center
  else: # Find it
    print >>out,"Finding NCS center as it is not supplied"
    ncs_center=find_ncs_center(map_data,crystal_symmetry=crystal_symmetry)
  print >>out,"Center of NCS (A): (%7.3f, %7.3f, %7.3f) " %(
    tuple(ncs_center))

  print >>out,"\nFinding %s NCS" %(ncs_type)

  ncs_list,ncs_type_list=get_ncs_list(ncs_type,
   ncs_center=ncs_center,
   helical_rot_deg=helical_rot_deg,
   two_fold_along_x=two_fold_along_x,
   op_max=op_max,
   helical_trans_z_angstrom=helical_trans_z_angstrom,
   out=out,
   )

  print >>out,"Total of %d NCS types to examine..." %(len(ncs_list))
  sites_orth=get_points_in_map(map_data,n=random_points,crystal_symmetry=crystal_symmetry)
  # some random points in the map

  # Now make sure symmetry applied to points in points_list gives similar values

  results_list=[]
  for ncs_obj,ncs_type in zip(ncs_list,ncs_type_list):
    score,cc_avg=score_ncs_in_map(map_data=map_data,ncs_object=ncs_obj,
      sites_orth=sites_orth,crystal_symmetry=crystal_symmetry,out=out)
    if score is None:
      print >>out,"ncs_type:",ncs_type," no score",ncs_obj.max_operators()
    else:
      results_list.append([score,cc_avg,ncs_obj,ncs_type])
  if not results_list:
    return None

  results_list.sort()
  results_list.reverse()

  # Rescore top n_rescore
  if n_rescore:
    print >>out,"Rescoring top %d results" %(min(n_rescore,len(results_list)))
    rescore_list=results_list[n_rescore:]
    new_sites_orth=get_points_in_map(
      map_data,n=10*random_points,crystal_symmetry=crystal_symmetry)
    new_sites_orth.extend(sites_orth)
    for orig_score,orig_cc_avg,ncs_obj,ncs_type in results_list[:n_rescore]:
      score,cc_avg=score_ncs_in_map(map_data=map_data,ncs_object=ncs_obj,
        sites_orth=new_sites_orth,crystal_symmetry=crystal_symmetry,out=out)
      if score is None:
        print >>out,"ncs_type:",ncs_type," no score",ncs_obj.max_operators()
      else:
        rescore_list.append([score,cc_avg,ncs_obj,ncs_type])
    rescore_list.sort()
    rescore_list.reverse()
    results_list=rescore_list

  print >>out,"Ranking of NCS types:"
  print >>out,"\n  SCORE    CC   OPERATORS     SYMMETRY"
  for score,cc_avg,ncs_obj,ncs_type in results_list:
    print >>out," %6.2f  %5.2f    %2d          %s" %(
       score,cc_avg,ncs_obj.max_operators(), ncs_type.strip(),)

  score,cc_avg,ncs_obj,ncs_info=results_list[0]

  # Optimize center if necessary
  if optimize_center:
    ncs_center,cc_avg,score,ncs_obj=optimize_center_position(map_data,sites_orth,
       crystal_symmetry,
       ncs_info,ncs_center,ncs_obj,score,cc_avg,
       helical_rot_deg=helical_rot_deg,
       two_fold_along_x=two_fold_along_x,
       op_max=op_max,
       helical_trans_z_angstrom=helical_trans_z_angstrom,out=out)
    print >>out,"New center: (%7.3f, %7.3f, %7.3f)" %(tuple(ncs_center))

  if cc_avg < min_ncs_cc:
    print >>out,"No suitable symmetry found with center of map as center...\n"
    return None

  print >>out,"\nBest NCS type is: ",
  print >>out,"\n  SCORE    CC   OPERATORS     SYMMETRY"
  print >>out," %6.2f  %5.2f    %2d          %s" %(
       score,cc_avg,ncs_obj.max_operators(), ncs_info.strip(),)
  return ncs_obj


def optimize_center_position(map_data,sites_orth,crystal_symmetry,
     ncs_info,ncs_center,ncs_obj,score,cc_avg,
     helical_rot_deg=None,
     two_fold_along_x=None,
     op_max=None,
     helical_trans_z_angstrom=None,out=sys.stdout):

  ncs_type=ncs_info.split()[0]
  print >>out,"Optimizing center position...type is %s" %(ncs_info)

  if len(ncs_info.split())>1 and ncs_info.split()[1]=='(a)':
    two_fold_along_x=True
  elif len(ncs_info.split())>1 and ncs_info.split()[1]=='(b)':
    two_fold_along_x=False
  else:
    two_fold_along_x=None

  best_center=matrix.col(ncs_center)
  best_ncs_obj=ncs_obj
  best_score=score
  best_cc_avg=cc_avg
  print >>out,"Starting center: (%7.3f, %7.3f, %7.3f)" %(tuple(best_center))
  from libtbx.utils import null_out
  scale=5.
  for itry in xrange(6):
    scale=scale/5.
    for i in xrange(-4,5):
     for j in xrange(-4,5):
      local_center=matrix.col(ncs_center)+matrix.col((scale*i,scale*j,0.,))
      ncs_list,ncs_type_list=get_ncs_list(ncs_type,
       ncs_center=local_center,
       helical_rot_deg=helical_rot_deg,
       two_fold_along_x=two_fold_along_x,
       op_max=op_max,
       helical_trans_z_angstrom=helical_trans_z_angstrom,
       out=null_out(),
       )
      ncs_obj=ncs_list[0]
      score,cc_avg=score_ncs_in_map(map_data=map_data,ncs_object=ncs_obj,
          sites_orth=sites_orth,crystal_symmetry=crystal_symmetry,out=out)
      if best_score is None or score>best_score:
        best_cc_avg=cc_avg
        best_score=score
        best_center=local_center
        best_ncs_obj=ncs_obj

  ncs_center=best_center
  cc_avg=best_cc_avg
  score=best_score
  ncs_obj=best_ncs_obj
  return best_center,best_cc_avg,best_score,best_ncs_obj



def score_ncs_in_map(map_data=None,ncs_object=None,sites_orth=None,
     crystal_symmetry=None,out=sys.stdout):
  ncs_group=ncs_object.ncs_groups()[0]
  all_value_lists=[]
  for c,t,r in zip(ncs_group.centers(),
                       ncs_group.translations_orth(),
                       ncs_group.rota_matrices()):
    new_sites_cart=flex.vec3_double()
    r_inv=r.inverse()
    for site in sites_orth:
      new_sites_cart.append(r_inv * (matrix.col(site) - t))
    # get value at new_sites cart and make sure they are all the same...
    new_sites_fract=crystal_symmetry.unit_cell().fractionalize(new_sites_cart)
    values=flex.double()
    for site_fract in new_sites_fract:
      values.append(map_data.value_at_closest_grid_point(site_fract))
    all_value_lists.append(values)
  a=all_value_lists[0]
  cc_avg=0.
  cc_low=None
  cc_n=0.
  for j in xrange(1,len(all_value_lists)):
      b=all_value_lists[j]
      cc=flex.linear_correlation(a,b).coefficient()
      cc_avg+=cc
      cc_n+=1.
      if cc_low is None or cc<cc_low:
        cc_low=cc
  cc_avg=cc_avg/max(1.,cc_n)
  if cc_n>0:
    import math
    return cc_low*math.sqrt(len(all_value_lists)),cc_avg
  else:
    return None,None


def get_points_in_map(map_data,n=None,max_tries_ratio=100,crystal_symmetry=None):
  map_1d=map_data.as_1d()
  map_mean=map_1d.min_max_mean().mean
  map_max=map_1d.min_max_mean().max
  points_list=flex.vec3_double()
  import random
  nu,nv,nw=map_data.all()
  xyz_fract=crystal_symmetry.unit_cell().fractionalize(tuple((17.4,27.40128571,27.32985714,)))
  for i in xrange(int(max_tries_ratio*n)): # max tries
    ix=random.randint(0,nu-1)
    iy=random.randint(0,nv-1)
    iz=random.randint(0,nw-1)
    xyz_fract=matrix.col((ix/nu,iy/nv,iz/nw,))
    value=map_data.value_at_closest_grid_point(xyz_fract)
    if value > map_mean and value <map_max:
      points_list.append(xyz_fract)
      if points_list.size()>=n: break
  sites_orth=crystal_symmetry.unit_cell().orthogonalize(points_list)
  return sites_orth



def get_ncs_list(ncs_type,
   ncs_center=None,
   helical_rot_deg=None,
   helical_trans_z_angstrom=None,
   op_max=None,
   two_fold_along_x=None,
    out=sys.stdout):
  ncs_list=[]
  ncs_type_list=[]
  all=False
  sym_type=None
  sym_n=None
  if ncs_type.lower() in ['all','any']:
    all=True
  elif ncs_type.lower() in ["i"]:
    sym_type='I'
  elif ncs_type.lower().startswith("d"):
    sym_type='D'
    sym_n=int(ncs_type[1:])
  elif ncs_type.lower().startswith("c"):
    sym_type='C'
    sym_n=int(ncs_type[1:])
  elif ncs_type.lower() in ['helical','helix']:
    sym_type='helical'

  print >>out,"Sym type: %s  Sym N: %s" %(
     sym_type,sym_n)

  if sym_n:
    i_start=sym_n
    i_end=sym_n
  else:
    i_start=2
    i_end=op_max

  from mmtbx.ncs.ncs import get_ncs_from_text, \
      get_c_symmetry,get_d_symmetry,get_helical_symmetry
  if sym_type=='I' or all:
    if two_fold_along_x is None or two_fold_along_x==False:
      ncs_list.append(get_ncs_from_text(text=icosahedral_text))
      ncs_type_list.append('I (b)')
    if two_fold_along_x is None or two_fold_along_x==True:
      ncs_list.append(get_ncs_from_text(text=icosahedral_text,
          rotate_about_z=90))
      ncs_type_list.append('I (a)')
  if sym_type=='C' or all:
    for i in xrange(i_start,i_end+1):
      ncs_list.append(get_c_symmetry(n=i))
      ncs_type_list.append('C%d ' %(i))
  if sym_type=='D' or all:
    for i in xrange(i_start,i_end+1):
      if two_fold_along_x is None or two_fold_along_x==True:
        ncs_list.append(get_d_symmetry(n=i,two_fold_along_x=True))
        ncs_type_list.append('D%d (a)' %(i))
      if two_fold_along_x is None or two_fold_along_x==False:
        ncs_list.append(get_d_symmetry(n=i,two_fold_along_x=False))
        ncs_type_list.append('D%d (b)' %(i))
  if sym_type=='helical':
    ncs_list.append(get_helical_symmetry(
     helical_rot_deg=helical_rot_deg,
     helical_trans_z_angstrom=helical_trans_z_angstrom,))
    ncs_type_list.append("Type: Helical %5.2f deg  %6.2f Z-trans " %(
       helical_rot_deg,helical_trans_z_angstrom))

  if ncs_center and tuple(ncs_center) != (0,0,0,):
    print >>out,"Offsetting NCS center by (%.2f, %.2f, %.2f) A " %(tuple(ncs_center))
    new_list=[]
    for ncs_obj in ncs_list:
      new_list.append(ncs_obj.coordinate_offset(coordinate_offset=ncs_center))
    ncs_list=new_list

  for ncs_obj in ncs_list:
    assert ncs_obj.is_helical_along_z() or ncs_obj.is_point_group_symmetry()
  return ncs_list,ncs_type_list


def get_params_from_args(args):
  command_line = iotbx.phil.process_command_line_with_files(
    map_file_def="input_files.map_file",
    seq_file_def="input_files.seq_file",
    pdb_file_def="input_files.pdb_in",
    ncs_file_def="input_files.ncs_file",
    args=args,
    master_phil=master_phil)

  return command_line.work.extract()


def get_mask_around_molecule(map_data=None,
        wang_radius=None,
        buffer_radius=None,
        crystal_symmetry=None, out=sys.stdout):
  # use iterated solvent fraction tool to identify mask around molecule
  try:
    from phenix.autosol.map_to_model import iterated_solvent_fraction
    solvent_fraction,mask=iterated_solvent_fraction(
      crystal_symmetry=crystal_symmetry,
      wang_radius=wang_radius,
      map_as_double=map_data,
      out=out)
  except Exception,e:
    solvent_fraction,mask=None,None

  # Now expand the mask to increase molecular region
  expand_size=estimate_expand_size(
       crystal_symmetry=crystal_symmetry,
       map_data=map_data,
       expand_target=buffer_radius,
       out=out)

  print >>out,\
    "Target mask expand size is %d based on buffer_radius of %7.1f A" %(
     expand_size,buffer_radius)

  co,sorted_by_volume,min_b,max_b=get_co(map_data=mask,
     threshold=0.5,wrapping=False)
  masked_fraction=sorted_by_volume[1][0]/mask.size()
  print >>out,"\nMasked fraction before buffering: %7.2f" %(masked_fraction)

  s=None
  for v1,i1 in sorted_by_volume[1:]:
    bool_region_mask = co.expand_mask(
      id_to_expand=i1, expand_size=expand_size)
    if s is None:
      s = (bool_region_mask==True)
    else:
      s |= (bool_region_mask==True)
  mask.set_selected(s,1)
  mask.set_selected(~s,0)
  masked_fraction=mask.count(1)/mask.size()
  print >>out,"Masked fraction after buffering:  %7.2f" %(masked_fraction)

  return mask

def get_mean_in_and_out(sel=None,
    map_data=None,
    out=sys.stdout):

  mean_value_in,fraction_in=get_mean_in_or_out(sel=sel,
    map_data=map_data,
    out=out)

  mean_value_out,fraction_out=get_mean_in_or_out(sel= ~sel,
    map_data=map_data,
    out=out)

  print >>out,\
    "\nMean inside mask: %7.2f  Outside mask: %7.2f  Fraction in: %7.2f" %(
     mean_value_in,mean_value_out,fraction_in)
  return mean_value_in,mean_value_out,fraction_in

def get_mean_in_or_out(sel=None,
    map_data=None,
    out=sys.stdout):
  masked_map=map_data.deep_copy()
  masked_map.set_selected(~sel,0)
  mean_after_zeroing_in_or_out=masked_map.as_1d().min_max_mean().mean
  masked_map.set_selected(sel,1)
  fraction_in_or_out=masked_map.as_1d().min_max_mean().mean
  if fraction_in_or_out >1.e-10:
    mean_value=mean_after_zeroing_in_or_out/fraction_in_or_out
  else:
    mean_value=None

  return mean_value,fraction_in_or_out

def apply_soft_mask(map_data=None,
          mask_data=None,
          rad_smooth=None,
          crystal_symmetry=None,
          set_outside_to_mean_inside=False,
          threshold=0.5,
          out=sys.stdout):

  # apply a soft mask based on mask_data to map_data.
  # set value outside mask==mean value inside mask or mean value outside mask

  #write_ccp4_map(crystal_symmetry,'map_data.ccp4',map_data)

  s = mask_data > threshold  # s marks inside mask 

  # get mean inside or outside mask
  print >>out,"\nStarting map values inside and outside mask:"
  mean_value_in,mean_value_out,fraction_in=get_mean_in_and_out(sel=s,
    map_data=map_data, out=out)

  print >>out,"\nMask inside and outside values"
  mean_value_in,mean_value_out,fraction_in=get_mean_in_and_out(sel=s,
    map_data=mask_data, out=out)

  # Smooth the mask in place. First make it a binary mask
  mask_data = mask_data.set_selected(~s, 0)  # outside mask==0
  mask_data = mask_data.set_selected( s, 1)
  #write_ccp4_map(crystal_symmetry,'mask_data.ccp4',mask_data)
  maptbx.unpad_in_place(map=mask_data)
  mask_data = maptbx.smooth_map(
    map              = mask_data,
    crystal_symmetry = crystal_symmetry,
    rad_smooth       = rad_smooth)
  
  print >>out,"\nSmoothed mask inside and outside values"
  mean_value_in,mean_value_out,fraction_in=get_mean_in_and_out(sel=s,
    map_data=mask_data, out=out)

  #write_ccp4_map(crystal_symmetry,'mask_smooth.ccp4',mask_data)
  
  # Now replace value outside mask with mean_value, value inside with current,
  #   smoothly going from one to the other based on mask_data

  outside_set_to_mean=map_data.deep_copy()
  outside_set_to_mean.set_selected( s, 0)
  if set_outside_to_mean_inside:
    outside_set_to_mean.set_selected(~s, mean_value_in)
  else:
    outside_set_to_mean.set_selected(~s, mean_value_out)

  masked_map= (map_data * mask_data )  +  (outside_set_to_mean * (1-mask_data))

  print >>out,"\nFinal mean value inside and outside mask:"
  mean_value_in,mean_value_out,fraction_in=get_mean_in_and_out(sel=s,
    map_data=map_data, out=out)
  
  #write_ccp4_map(crystal_symmetry,'masked_map.ccp4',masked_map)

  return masked_map

def estimate_expand_size(
       crystal_symmetry=None,
       map_data=None,
       expand_target=None,
       out=sys.stdout):
    abc = crystal_symmetry.unit_cell().parameters()[:3]
    N_ = map_data.all()
    nn=0.
    for i in xrange(3):
      delta=abc[i]/N_[i]
      nn+=expand_target/delta
    nn=max(1,int(0.5+nn/3.))
    print >>out,\
      "Expand size (grid units): %d (about %4.1f A) " %(
      nn,nn*abc[0]/N_[0])
    return max(1,nn)

def get_params(args,map_data=None,crystal_symmetry=None,out=sys.stdout):

  params=get_params_from_args(args)

  print >>out,"\nSegment_and_split_map\n"
  print >>out,"Command used: %s\n" %(
   " ".join(['segment_and_split_map']+args))
  master_params.format(python_object=params).show(out=out)

  from cctbx.maptbx.auto_sharpen import set_sharpen_params
  params=set_sharpen_params(params,out)

  if not params.crystal_info.resolution and (
     params.map_modification.b_iso is not None or \
      params.map_modification.auto_sharpen
      or params.map_modification.resolution_dependent_b or
      params.map_modification.b_sharpen):
    raise Sorry("Need resolution for segment_and_split_map with sharpening")

  if params.map_modification.auto_sharpen and (
      params.map_modification.b_iso is not None or
      params.map_modification.b_sharpen is not None or
      params.map_modification.resolution_dependent_b is not None):
    print >>out,"Turning off auto_sharpen as it is not compatible with "+\
        "b_iso, \nb_sharpen, or resolution_dependent_b"
    params.map_modification.auto_sharpen=False

  if params.map_modification.soft_mask and not params.segmentation.density_select:
    raise Sorry("Need to specify density_select=True for soft_mask")

  if params.output_files.output_directory and  \
     not os.path.isdir(params.output_files.output_directory):
      os.mkdir(params.output_files.output_directory)
  if not params.output_files.output_directory:
    params.output_files.output_directory=""

  # Test to see if we can use adjusted_sa as target and use box_map with it
  if (params.map_modification.residual_target=='adjusted_sa' or
     params.map_modification.sharpening_target=='adjusted_sa') and \
     params.map_modification.box_in_auto_sharpen:
    print >>out,"Checking to make sure we can use adjusted_sa as target...",
    try:
      from phenix.autosol.map_to_model import iterated_solvent_fraction
    except Exception, e:
      raise Sorry(
      "Please either set box_in_auto_sharpen=False or \n"+\
      "set residual_target=kurtosis and sharpening_target=kurtosis")
    print >>out,"OK"

  half_map_data_list=[]

  if params.input_files.info_file:
    map_data=None
    pdb_hierarchy=None
    from libtbx import easy_pickle
    print >>out,"Loading tracking data from %s" %(
      params.input_files.info_file)
    tracking_data=easy_pickle.load(params.input_files.info_file)
    return params,map_data,half_map_data_list,pdb_hierarchy,tracking_data
  else:
    tracking_data=info_object()
    tracking_data.set_params(params)

  # PDB file
  print >>out,"\nInput PDB file to be shifted only: %s\n" %(
     params.input_files.pdb_file)
  if params.input_files.pdb_file:
    pdb_inp = iotbx.pdb.input(file_name=params.input_files.pdb_file)
    pdb_hierarchy = pdb_inp.construct_hierarchy()
    pdb_atoms = pdb_hierarchy.atoms()
    pdb_atoms.reset_i_seq()
    tracking_data.set_input_pdb_info(file_name=params.input_files.pdb_file,
      n_residues=pdb_hierarchy.overall_counts().n_residues)
  else:
    pdb_hierarchy=None

  if map_data:
    pass # ok
  elif params.input_files.map_file:
    from iotbx import ccp4_map
    ccp4_map=iotbx.ccp4_map.map_reader(
    file_name=params.input_files.map_file)
    crystal_symmetry=crystal.symmetry(ccp4_map.unit_cell().parameters(),
      ccp4_map.space_group_number)
    map_data=ccp4_map.map_data()
  else:
    raise Sorry("Need ccp4 map")

  if params.input_files.half_map_file:
    if len(params.input_files.half_map_file) != 2: 
      raise Sorry("Please supply none or two half_map_file values")

    from iotbx import ccp4_map
    half_map_data_list=[]
    half_map_data_list.append(iotbx.ccp4_map.map_reader(
       file_name=params.input_files.half_map_file[0]).map_data())
    half_map_data_list.append(iotbx.ccp4_map.map_reader(
       file_name=params.input_files.half_map_file[0]).map_data())


  if params.map_modification.magnification and \
       params.map_modification.magnification!=1.0:
    print >>out,"\nAdjusting magnification by %7.3f\n" %(
       params.map_modification.magnification)

    if params.input_files.ncs_file:
      # Magnify ncs
      print >>out,"NCS before applying magnification..."
      ncs_obj,dummy_tracking_data=get_ncs(params,None,out=out)
      ncs_obj.format_all_for_group_specification(out=out)
      ncs_obj=ncs_obj.adjust_magnification(
        magnification=params.map_modification.magnification)
      if params.output_files.magnification_ncs_file:
        file_name=os.path.join(params.output_files.output_directory,
          params.output_files.magnification_ncs_file)
        print >>out,"Writing NCS after magnification of %7.3f to %s" %(
          params.map_modification.magnification,file_name)
        ncs_obj.format_all_for_group_specification(out=out)
        ncs_obj.format_all_for_group_specification(file_name=file_name)
        params.input_files.ncs_file=file_name
      else:
        raise Sorry("Need magnification_ncs_file defined if magnification is"+
          " applied \nto input NCS file")

    # Magnify map
    shrunk_uc = []
    for i in range(3):
      shrunk_uc.append(
       crystal_symmetry.unit_cell().parameters()[i] *
          params.map_modification.magnification )
    uc_params=crystal_symmetry.unit_cell().parameters()
    from cctbx import uctbx
    new_unit_cell=uctbx.unit_cell(
      parameters=(shrunk_uc[0],shrunk_uc[1],shrunk_uc[2],
          uc_params[3],uc_params[4],uc_params[5]))
    print >>out,\
      "Original unit cell: (%7.4f, %7.4f, %7.4f, %7.4f, %7.4f, %7.4f)" %(
      crystal_symmetry.unit_cell().parameters())
    crystal_symmetry=crystal.symmetry(
      unit_cell=new_unit_cell,
      space_group=crystal_symmetry.space_group())
    print >>out,\
      "New unit cell:      (%7.4f, %7.4f, %7.4f, %7.4f, %7.4f, %7.4f)" %(
      crystal_symmetry.unit_cell().parameters())

    if params.output_files.magnification_map_file:
      file_name=os.path.join(params.output_files.output_directory,
        params.output_files.magnification_map_file)
      # write out magnified map (our working map) (before shifting it)
      print >>out,"\nWriting magnification map (input map with "+\
        "magnification of %7.3f \n" %(params.map_modification.magnification) +\
        "applied) to %s \n" %(file_name)
      write_ccp4_map(crystal_symmetry,file_name,map_data)
      params.input_files.map_file=file_name
    else:
      raise Sorry("Need a file name to write out magnification_map_file")
    params.map_modification.magnification=None  # no longer need it.

  tracking_data.set_input_map_info(file_name=params.input_files.map_file,
    crystal_symmetry=crystal_symmetry,
    origin=map_data.origin(),
    all=map_data.all())
  tracking_data.set_crystal_symmetry(crystal_symmetry=crystal_symmetry)
  tracking_data.set_original_crystal_symmetry(crystal_symmetry=crystal_symmetry)

  # Save center of map
  map_ncs_center=get_center_of_map(map_data,crystal_symmetry)

  # either use map_box with density_select=True or just shift the map
  if  params.segmentation.density_select:
    print >>out,"\nTrimming map to density..."
    args=["density_select=True","output_format=ccp4"]
    if params.segmentation.density_select_threshold is not None:
      print >>out,"Threshold for density selection will be: %6.2f \n"%(
       params.segmentation.density_select_threshold)
      args.append("density_select_threshold=%s" %(
         params.segmentation.density_select_threshold))

    if params.segmentation.get_half_height_width is not None:
      args.append("get_half_height_width=%s" %(
        params.segmentation.get_half_height_width))
    if params.input_files.ncs_file:
      args.append("ncs_file=%s" %(params.input_files.ncs_file))
    if params.input_files.pdb_file:
      args.append("pdb_file=%s" %(params.input_files.pdb_file))
    args.append("ccp4_map_file=%s" %(params.input_files.map_file))
    file_name_prefix=os.path.join(params.output_files.output_directory,
       "density_select")
    args.append("output_file_name_prefix=%s" %(file_name_prefix))
    from mmtbx.command_line.map_box import run as run_map_box
    box=run_map_box(args,crystal_symmetry=crystal_symmetry,log=out)
    origin_shift=box.total_shift_cart
    # Note: moving cell with (0,0,0) in middle to (0,0,0) at corner means
    #   total_shift_cart and origin_shift both positive
    map_data=box.map_box.as_double()
    map_data=scale_map(map_data,out=out)
    crystal_symmetry=box.box_crystal_symmetry
    print >>out,"New unit cell: %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f " %(
      crystal_symmetry.unit_cell().parameters())
    tracking_data.set_crystal_symmetry(crystal_symmetry=crystal_symmetry)
    print >>out, "Moving origin to (0,0,0)"
    print >>out,"Adding (%8.2f,%8.2f,%8.2f) to all coordinates\n"%(
        origin_shift)
    # NOTE: size and cell params are now different!

    new_half_map_data_list=[]
    for hm in half_map_data_list:
      hm=hm.shift_origin() # shift if necessary
      new_half_map_data_list.append(
      box.cut_and_copy_map(map_data=hm).as_double())
    half_map_data_list=new_half_map_data_list

    if params.map_modification.soft_mask:
      if not params.crystal_info.resolution:
        raise Sorry("Need resolution for soft_mask")

      rad_smooth=params.crystal_info.resolution
     
      print >>out,"\nApplying soft mask with smoothing radius of %s\n" %(
        rad_smooth)
      if params.crystal_info.wang_radius:
        wang_radius=params.crystal_info.wang_radius
      else:
        wang_radius=1.5*params.crystal_info.resolution

      if params.crystal_info.buffer_radius:
        buffer_radius=params.crystal_info.buffer_radius
      else:
        buffer_radius=2.*params.crystal_info.resolution

      mask_data=get_mask_around_molecule(map_data=map_data,
        crystal_symmetry=crystal_symmetry,
        wang_radius=wang_radius,
        buffer_radius=buffer_radius,
        out=out)
      if mask_data:
        map_data=apply_soft_mask(map_data=map_data,
          mask_data=mask_data.as_double(),
          rad_smooth=rad_smooth,
          crystal_symmetry=crystal_symmetry,
          out=out)

        new_half_map_data_list=[]
        for half_map in half_map_data_list:
          half_map=apply_soft_mask(map_data=half_map,
            mask_data=mask_data.as_double(),
            rad_smooth=rad_smooth,
            crystal_symmetry=crystal_symmetry,
            out=out)
          new_half_map_data_list.append(half_map)
        half_map_data_list=new_half_map_data_list
      else:
        print >>out,"Unable to get mask...skipping"


  else:  # shift if necessary...
    shift_needed = not \
        (map_data.focus_size_1d() > 0 and map_data.nd() == 3 and
         map_data.is_0_based())

    a,b,c = crystal_symmetry.unit_cell().parameters()[:3]
    N_ = map_data.all()
    O_ =map_data.origin()
    sx,sy,sz= O_[0]/N_[0], O_[1]/N_[1], O_[2]/N_[2]
    # Note: If (0,0,0) is in the middle of the box, origin at sx,sy,sz
    #  is negative, shift of coordinates will be positive
    sx_cart,sy_cart,sz_cart=crystal_symmetry.unit_cell().orthogonalize(
       [sx,sy,sz])
    print >>out,"Origin for input map is at (%8.2f,%8.2f,%8.2f)" % (
      sx_cart,sy_cart,sz_cart)
    print >>out,"Cell dimensions of this map are: (%8.2f,%8.2f,%8.2f)" % (a,b,c)
    if shift_needed:
      if(not crystal_symmetry.space_group().type().number() in [0,1]):
          raise RuntimeError("Not implemented")
      origin_shift=[-sx_cart,-sy_cart,-sz_cart] # positive if (0,0,0) in middle
      print >>out,"Adding (%8.2f,%8.2f,%8.2f) to all coordinates"%(
        tuple(origin_shift))+" to put origin at (0,0,0)\n"

      map_data=map_data.shift_origin()
      new_half_map_data_list=[]
      for hm in half_map_data_list:
        new_half_map_data_list.append(hm.shift_origin())
      half_map_data_list=new_half_map_data_list
    else:
      origin_shift=(0.,0.,0.)

  # Set origin shift now
  tracking_data.set_origin_shift(origin_shift)

  map_ncs_center=matrix.col(map_ncs_center)+matrix.col(origin_shift) # New ctr

  # Get NCS operators if needed and user did not supply them
  if params.reconstruction_symmetry.ncs_type and (not params.input_files.ncs_file):
    center_try_list=[True,False]
  elif params.reconstruction_symmetry.optimize_center:
    center_try_list=[None]
  else:
    center_try_list=[]

  found_ncs=False
  if center_try_list:
    looking_for_ncs=True
  else:
    looking_for_ncs=False

  for use_center_of_map in center_try_list: # only if ncs_file missing
    new_ncs_obj=get_ncs_from_map(map_data=map_data,
      map_ncs_center=map_ncs_center,
      ncs_type=params.reconstruction_symmetry.ncs_type,
      ncs_center=params.reconstruction_symmetry.ncs_center,
      optimize_center=params.reconstruction_symmetry.optimize_center,
      helical_rot_deg=params.reconstruction_symmetry.helical_rot_deg,
      helical_trans_z_angstrom=params.reconstruction_symmetry.helical_trans_z_angstrom,
      n_rescore=params.reconstruction_symmetry.n_rescore,
      random_points=params.reconstruction_symmetry.random_points,
      op_max=params.reconstruction_symmetry.op_max,
      two_fold_along_x=params.reconstruction_symmetry.two_fold_along_x,
      crystal_symmetry=crystal_symmetry,
      use_center_of_map_as_center=use_center_of_map,
      out=out
      )
    if new_ncs_obj:
      # offset this back to where it would have been before the origin offset..
      new_ncs_obj=new_ncs_obj.coordinate_offset(
       coordinate_offset=-1*matrix.col(origin_shift))
      file_name=os.path.join(params.output_files.output_directory,
          'ncs_from_map.ncs_spec')
      f=open(file_name,'w')
      new_ncs_obj.format_all_for_group_specification(out=f)
      f.close()
      print >>out,"Wrote NCS operators (for original map) to %s" %(file_name)
      params.input_files.ncs_file=file_name
      found_ncs=True
      break # found it, no need to continue

  if looking_for_ncs and (not found_ncs) and \
         params.reconstruction_symmetry.ncs_type != 'ANY':
      raise Sorry(
        "Unable to identify %s symmetry automatically in this map." %(
        params.reconstruction_symmetry.ncs_type)+
        "\nPlease supply an ncs_file with symmetry matrices.")

  if params.segmentation.expand_size is None:
    params.segmentation.expand_size=estimate_expand_size(
       crystal_symmetry=crystal_symmetry,
       map_data=map_data,
       expand_target=params.segmentation.expand_target,
       out=out)

  return params,map_data,half_map_data_list,pdb_hierarchy,tracking_data

def get_ncs(params,tracking_data=None,ncs_object=None,out=sys.stdout):
  file_name=params.input_files.ncs_file
  if file_name: print >>out,"Reading ncs from %s" %(file_name)
  is_helical_symmetry=None
  if not ncs_object and not file_name: # No ncs supplied...use just 1 ncs copy..
    from mmtbx.ncs.ncs import ncs
    ncs_object=ncs()
    ncs_object.set_unit_ncs()
    #ncs_object.display_all(log=out)
  elif not ncs_object and not os.path.isfile(file_name):
    raise Sorry("The ncs file %s is missing" %(file_name))
  else: # get the ncs
    if not ncs_object:
      from mmtbx.ncs.ncs import ncs
      ncs_object=ncs()
      try: # see if we can read biomtr records
        pdb_inp=iotbx.pdb.input(file_name=file_name)
        ncs_object.ncs_from_pdb_input_BIOMT(pdb_inp=pdb_inp,log=out)
      except Exception,e: # try as regular ncs object
        ncs_object.read_ncs(file_name=file_name,log=out)
      #ncs_object.display_all(log=out)
    if ncs_object.max_operators()==0:
      ncs_object=ncs()
      ncs_object.set_unit_ncs()
    print >>out,"\nTotal of %d NCS operators read\n" %(
      ncs_object.max_operators())
    if ncs_object.is_helical_along_z(abs_tol_t=.50):
      print >>out,"This NCS is helical symmetry"
      is_helical_symmetry=True
    elif ncs_object.is_point_group_symmetry(abs_tol_t=.50):
      print >>out,"This NCS is point-group symmetry"
    elif params.crystal_info.is_crystal:
      print >>out,"This NCS is crystal symmetry"
    else:
      raise Sorry("Need point-group or helical symmetry.")
  if not ncs_object or ncs_object.max_operators()<1:
    raise Sorry("Need ncs information from an ncs_info file")
  if tracking_data:
    tracking_data.set_input_ncs_info(file_name=file_name,
      number_of_operators=ncs_object.max_operators())

  if tracking_data and is_helical_symmetry: # update shifted_ncs_info
    if tracking_data.shifted_ncs_info: # XXX may not be needed
       shifted=True
    else:
       shifted=False
    print >>out,"Updating NCS info (shifted=%s)" %(shifted)
    tracking_data.update_ncs_info(is_helical_symmetry=True,shifted=shifted)

    if tracking_data.input_map_info and tracking_data.input_map_info.all:
      z_range=tracking_data.input_map_info.crystal_symmetry.unit_cell(). \
         parameters()[2]
      print >>out,"Extending NCS operators to entire cell (z_range=%.1f)" %(
         z_range)
      ncs_object.extend_helix_operators(z_range=z_range)
      ncs_object.display_all()
      tracking_data.update_ncs_info(
        number_of_operators=ncs_object.max_operators(),is_helical_symmetry=True,
        shifted=shifted)

  return ncs_object,tracking_data

def score_threshold(b_vs_region=None,threshold=None,
     sorted_by_volume=None,n_residues=None,
     ncs_copies=None,
     fraction_occupied=None,
     solvent_fraction=None,
     map_data=None,
     residues_per_region=50,
     min_volume=None,
     min_ratio=None,
     max_ratio_to_target=None,
     min_ratio_to_target=None,
     weight_score_grid_points=1.,
     weight_score_ratio=1.0,
     weight_near_one=0.1,
     min_ratio_of_ncs_copy_to_first=None,
     target_in_all_regions=None,
     crystal_symmetry=None,
     chain_type=None,
     out=sys.stdout):
   # We want about 1 region per 50-100 residues for the biggest region.
   # One possibility is to try to maximize the median size of the N top
   # regions, where N=number of expected regions= n_residues/residues_per_region

   # Also note we have an idea how big a region should be (how many
   # grid points) if we make an assumption about the fractional volume that
   # should be inside a region compared to the total volume of protein/nucleic
   # acid in the region...this gives us target_in_top_regions points.
   # So using this, make the median size as close to target_in_top_regions as
   # we can.

   # If we have solvent fraction but not ncs_copies or n_residues, guess the
   #  number of residues and ncs copies from the volume
   if ncs_copies is not None and n_residues is not None:
     expected_regions=max(ncs_copies,
      max(1,int(0.5+n_residues/residues_per_region)))
   else:
      if chain_type is None: chain_type="PROTEIN"
      assert crystal_symmetry is not None
      assert solvent_fraction is not None
      volume_per_residue,nres,chain_type=get_volume_of_seq(
          "A",chain_type=chain_type,out=out)
      expected_regions=max(1,int(0.5+(1-solvent_fraction)*\
        crystal_symmetry.unit_cell().volume()/volume_per_residue ))
      ncs_copies=1

   target_in_top_regions=target_in_all_regions/expected_regions

   nn=len(sorted_by_volume)-1 # first one is total
   ok=True

   too_low=None  # marker for way too low
   too_high=None

   if nn < ncs_copies:
     ok=False #return  # not enough

   v1,i1=sorted_by_volume[1]
   if v1 < min_volume:
     ok=False #return

   if v1 > max_ratio_to_target*target_in_top_regions:
     ok=False #return
     too_low=True

   if v1 < min_volume or v1 < 0.1*min_ratio_to_target*target_in_top_regions:
     # way too high
     too_high=True


   # there should be about ncs_copies copies of each size region if ncs_copies>1
   if ncs_copies>1:
     v2,i2=sorted_by_volume[max(1,min(ncs_copies,nn))]
     score_ratio=v2/v1  # want it to be about 1
     if score_ratio < min_ratio_of_ncs_copy_to_first:
       ok=False #return  # not allowed
   else:
     score_ratio=1.0 # for ncs_copies=1

   nn2=min(nn,max(1,(expected_regions+1)//2))
   median_number,iavg=sorted_by_volume[nn2]

   # number in each region should be about target_in_top_regions

   if median_number > target_in_top_regions:
     score_grid_points=target_in_top_regions/max(1.,median_number)
   else:
     score_grid_points=median_number/target_in_top_regions

   if v1> target_in_top_regions:
     score_grid_points_b=target_in_top_regions/max(1.,v1)
   else:
     score_grid_points_b=v1/target_in_top_regions

   score_grid_points=0.5*(score_grid_points+score_grid_points_b)

   score_grid_points=score_grid_points**2  # maybe even **3

   if threshold>1.:
     score_near_one=1./threshold
   else:
     score_near_one=threshold

   # Normalize weight_score_ratio by target_in_top_regions:
   sc=min(1.,0.5*median_number/max(1,target_in_top_regions))
   overall_score=(
     (sc*weight_score_ratio*score_ratio+
     weight_score_grid_points*score_grid_points+
     weight_near_one*score_near_one
       ) /
     (weight_score_ratio+weight_score_grid_points+weight_near_one))

   half_expected_regions=max(1,(1+expected_regions)//2)
   ratio=sorted_by_volume[min(len(sorted_by_volume)-1,half_expected_regions)][0]/v1

   if ok and v1 >= target_in_top_regions/2 and \
        len(sorted_by_volume)>half_expected_regions:
     last_volume=sorted_by_volume[half_expected_regions][0]
     if ratio >=min_ratio and \
         last_volume>=min_volume:
       has_sufficient_regions=True
     else:
       has_sufficient_regions=False
   else:
       has_sufficient_regions=False


   print >>out,\
   "%7.2f  %5.2f   %5d     %4d    %5d     %5d     %6.3f   %5s    %5.3f  %s  %s" %(
       b_vs_region.b_iso,threshold,target_in_top_regions,expected_regions,
       v1,median_number,ratio,has_sufficient_regions,overall_score,ok,nn)

   if not b_vs_region.b_iso in b_vs_region.b_vs_region_dict.keys():
     b_vs_region.b_vs_region_dict[b_vs_region.b_iso]={}
     b_vs_region.sa_sum_v_vs_region_dict[b_vs_region.b_iso]={}
     b_vs_region.sa_nn_vs_region_dict[b_vs_region.b_iso]={}
     b_vs_region.sa_ratio_b_vs_region_dict[b_vs_region.b_iso]={}
   b_vs_region.b_vs_region_dict[b_vs_region.b_iso][threshold]=nn
   b_vs_region.sa_nn_vs_region_dict[b_vs_region.b_iso][threshold]=None
   b_vs_region.sa_ratio_b_vs_region_dict[b_vs_region.b_iso][threshold]=None

   return overall_score,has_sufficient_regions,\
      too_low,too_high,expected_regions,ok


def choose_threshold(b_vs_region=None,map_data=None,
     fraction_occupied=None,
     solvent_fraction=None,
     n_residues=None,
     ncs_copies=None,
     scale=0.95,
     calculate_sa=None, # calculate surface area of top sa_percent of target
     sa_percent=None, # calculate surface area of top sa_fraction of target
     density_threshold=None,
     starting_density_threshold=None,
     wrapping=None,
     residues_per_region=None,
     min_volume=None,
     min_ratio=None,
     max_ratio_to_target=None,
     min_ratio_to_target=None,
     min_ratio_of_ncs_copy_to_first=None,
     verbose=None,
     crystal_symmetry=None,
     chain_type=None,
     out=sys.stdout):

  best_threshold=None
  best_threshold_has_sufficient_regions=None
  best_score=None
  best_ok=None

  if not ncs_copies: ncs_copies=1

  print >>out,"\nChecking possible cutoffs for region identification"
  print >>out,"Scale: %7.3f" %(scale)
  used_ranges=[]

  # Assume any threshold that is lower than a threshold that gave a non-zero value
  #  and is zero is an upper bound on the best value.  Same the other way around
  upper_bound=1000
  lower_bound=0.0001
  best_nn=None

  if density_threshold is not None: # use it
     print >>out,"\nUsing input threshold of %5.2f " %(
      density_threshold)
     n_range_low_high_list=[[0,0]] # use as is
  else:
    n_range_low_high_list=[[-16,4],[-32,16],[-64,80]]
    if starting_density_threshold is not None:
      starting_density_threshold=starting_density_threshold
      print >>out,"Starting density threshold is: %7.3f" %(
         starting_density_threshold)
    else:
      starting_density_threshold=1.0
  if verbose:
    local_out=out
  else:
    from libtbx.utils import null_out
    local_out=null_out()

  target_in_all_regions=map_data.size()*fraction_occupied*(1-solvent_fraction)
  print >>local_out,"\nTarget number of points in all regions: %.0f" %(
    target_in_all_regions)


  local_threshold=find_threshold_in_map(target_points=int(
       target_in_all_regions),map_data=map_data)
  print >>out,"Cutoff will be threshold of %7.2f marking %7.1f%% of cell" %(
            local_threshold,100.*(1.-solvent_fraction))

  print >>local_out,\
    "B-iso  Threshold  Target    N     Biggest   Median     Ratio   Enough  Score   OK  Regions"
  unique_expected_regions=None
  for n_range_low,n_range_high in n_range_low_high_list:
    last_score=None
    for nn in xrange(n_range_low,n_range_high+1):
      if nn in used_ranges: continue
      used_ranges.append(nn)
      if density_threshold is not None:
        threshold=density_threshold
      else:
        threshold=starting_density_threshold*(scale**nn)
      if threshold < lower_bound or threshold > upper_bound:
        continue
      co = maptbx.connectivity(map_data=map_data.deep_copy(),
         threshold=threshold,
         wrapping=wrapping)
      z = zip(co.regions(),range(0,co.regions().size()))
      sorted_by_volume = sorted(z, key=lambda x: x[0], reverse=True)
      if len(sorted_by_volume)<2:
        score,has_sufficient_regions,too_low,too_high,expected_regions,ok=\
          None,None,None,None,None,None
        continue # don't go on
      else:
        score,has_sufficient_regions,too_low,too_high,expected_regions,ok=\
           score_threshold(b_vs_region=b_vs_region,
         threshold=threshold,
         sorted_by_volume=sorted_by_volume,
         fraction_occupied=fraction_occupied,
         solvent_fraction=solvent_fraction,
         residues_per_region=residues_per_region,
         min_volume=min_volume,
         min_ratio=min_ratio,
         max_ratio_to_target=max_ratio_to_target,
         min_ratio_to_target=min_ratio_to_target,
         min_ratio_of_ncs_copy_to_first=min_ratio_of_ncs_copy_to_first,
         ncs_copies=ncs_copies,
         n_residues=n_residues,
         map_data=map_data,
         target_in_all_regions=target_in_all_regions,
         crystal_symmetry=crystal_symmetry,
         chain_type=chain_type,
         out=local_out)
      if expected_regions:
        unique_expected_regions=max(1,
         (ncs_copies-1+expected_regions)//ncs_copies)
      if too_high and threshold<upper_bound:
        upper_bound=threshold
      if too_low and threshold>lower_bound:
        lower_bound=threshold
      if score is None:
        if best_threshold and best_threshold_has_sufficient_regions:
          if threshold >best_threshold: # new upper bound
           upper_bound=threshold
          elif threshold <best_threshold: # new lower bound
           lower_bound=threshold
      elif  (ok or not best_ok) and  \
            (best_score is None or score > best_score):
        best_threshold=threshold
        best_threshold_has_sufficient_regions=has_sufficient_regions
        best_score=score
        best_ok=ok

  if best_threshold is not None:
    print >>out,"\nBest threshold: %5.2f\n" %(best_threshold)
    return best_threshold,unique_expected_regions,best_score,best_ok
  elif density_threshold is not None: # use it anyhow
    return density_threshold,unique_expected_regions,None,None
  else:
    return None,unique_expected_regions,None,None

def get_co(map_data=None,threshold=None,wrapping=None):
  co=maptbx.connectivity(map_data=map_data,threshold=threshold,
         wrapping=wrapping)
  z = zip(co.regions(),range(0,co.regions().size()))
  sorted_by_volume = sorted(z, key=lambda x: x[0], reverse=True)
  min_b, max_b = co.get_blobs_boundaries_tuples() # As grid points, not A
  return co,sorted_by_volume,min_b,max_b

def get_connectivity(b_vs_region=None,
     map_data=None,
     solvent_fraction=None,
     n_residues=None,
     ncs_copies=None,
     fraction_occupied=None,
     iterate_with_remainder=None,
     min_volume=None,
     min_ratio=None,
     wrapping=None,
     residues_per_region=None,
     max_ratio_to_target=None,
     min_ratio_to_target=None,
     min_ratio_of_ncs_copy_to_first=None,
     starting_density_threshold=None,
     density_threshold=None,
     crystal_symmetry=None,
     chain_type=None,
     verbose=None,
     out=sys.stdout):
  print >>out,"\nGetting connectivity"
  # Normalize map data now to SD of the part that is not solvent
  map_data=renormalize_map_data(
     map_data=map_data,solvent_fraction=solvent_fraction)

  # Try connectivity at various thresholds
  # Choose one that has about the right number of grid points in top regions
  scale=0.95
  best_threshold=None
  best_scale=scale
  best_score=None
  best_ok=None
  best_unique_expected_regions=None
  for ii in xrange(3):
    threshold,unique_expected_regions,score,ok=choose_threshold(
     density_threshold=density_threshold,
     starting_density_threshold=starting_density_threshold,
     b_vs_region=b_vs_region,
     map_data=map_data,
     n_residues=n_residues,
     ncs_copies=ncs_copies,
     fraction_occupied=fraction_occupied,
     solvent_fraction=solvent_fraction,
     scale=scale,
     wrapping=wrapping,
     residues_per_region=residues_per_region,
     min_volume=min_volume,
     min_ratio=min_ratio,
     max_ratio_to_target=max_ratio_to_target,
     min_ratio_to_target=min_ratio_to_target,
     min_ratio_of_ncs_copy_to_first=min_ratio_of_ncs_copy_to_first,
     crystal_symmetry=crystal_symmetry,
     chain_type=chain_type,
     verbose=verbose,
     out=out)
    # Take it if it improves (score, ok)
    if threshold is not None:
     if best_score is None or  \
      ((ok or not best_ok) and (score > best_score)):
      best_score=score
      best_unique_expected_regions=unique_expected_regions
      best_ok=ok
      best_threshold=threshold
      best_scale=scale
    if best_ok or density_threshold is not None:
      break
    else:
      scale=scale**0.333 # keep trying

  if best_threshold is None or (
      density_threshold is not None and best_score is None):
    if iterate_with_remainder: # on first try failed
      raise Sorry("No threshold found...try with density_threshold=xxx")
    else: # on iteration...ok
      print >>out,"Note: No threshold found"
      return None,None,None,None,None,None,None,None
  else:
    starting_density_threshold=best_threshold
    # try it next time

  co,sorted_by_volume,min_b,max_b=get_co(
    map_data=map_data,threshold=best_threshold,wrapping=wrapping)

  return co,sorted_by_volume,min_b,max_b,best_unique_expected_regions,\
      best_score,threshold,starting_density_threshold

def get_volume_of_seq(text,chain_type=None,out=sys.stdout):
  from iotbx.bioinformatics import chain_type_and_residues
  # get chain type and residues (or use given chain type and count residues)
  chain_type,n_residues=chain_type_and_residues(text=text,chain_type=chain_type)
  if chain_type is None and n_residues is None:
    return None,None,None
  if chain_type=='PROTEIN':
    mw_residue=110.0  # from $CDOC/matthews.doc
    density_factor=1.23   # 1.66/DENSITY-OF-PROTEIN=1.66/1.35
  else:
    mw_residue=330.0  # guess for DNA/RNA
    density_factor=1.15   # 1.66/DENSITY-OF-DNA=1.66/1.45
  return len(text)*density_factor*mw_residue,len(text),chain_type

def create_rna_dna(cns_dna_rna_residue_names):
  dd={}
  for key in cns_dna_rna_residue_names.keys():
    dd[cns_dna_rna_residue_names[key]]=key
  return dd

def get_solvent_fraction(params,
     ncs_object=None,ncs_copies=None,
     crystal_symmetry=None,tracking_data=None,out=sys.stdout):
  if tracking_data and not crystal_symmetry:
    crystal_symmetry=tracking_data.crystal_symmetry
  map_volume=crystal_symmetry.unit_cell().volume()
  if tracking_data and not ncs_copies:
    ncs_copies=tracking_data.input_ncs_info.original_number_of_operators
  if not ncs_copies: ncs_copies=1
  if not params.input_files.seq_file:
    raise Sorry("Please specify a sequence file with seq_file=myseq.seq")
  elif not os.path.isfile(params.input_files.seq_file):
    raise Sorry(
     "The sequence file '%s' is missing." %(params.input_files.seq_file))
  seq_as_string=open(params.input_files.seq_file).read()
  seq_as_string=">\n"+seq_as_string  # so it always starts with >
  seq_as_string=seq_as_string.replace("\n\n","\n>\n") # blank lines are like >
  spl=seq_as_string.split(">")
  volume_of_chains=0.
  n_residues=0
  chain_types_considered=[]
  for s in spl:
    if not s: continue
    ss="".join(s.splitlines()[1:])
    volume,nres,chain_type=get_volume_of_seq(ss,
      chain_type=params.crystal_info.chain_type,out=out)
    if volume is None: continue
    volume_of_chains+=volume
    n_residues+=nres
    if not chain_type in chain_types_considered:
      chain_types_considered.append(chain_type)
  chain_types_considered.sort()
  print >>out,"\nChain types considered: %s\n" %(
      " ".join(chain_types_considered))
  volume_of_molecules=volume_of_chains*ncs_copies
  n_residues_times_ncs=n_residues*ncs_copies
  solvent_fraction=1.-(volume_of_molecules/map_volume)
  solvent_fraction=max(0.001,min(0.999,solvent_fraction))
  print >>out, \
    "Cell volume: %.1f  NCS copies: %d   Volume of unique chains: %.1f" %(
     map_volume,ncs_copies,volume_of_chains)
  print >>out,\
    "Total residues: %d  Volume of all chains: %.1f  Solvent fraction: %.3f "%(
       n_residues_times_ncs,volume_of_molecules,solvent_fraction)
  if tracking_data:
    tracking_data.set_input_seq_info(file_name=params.input_files.seq_file,
    n_residues=n_residues)
    tracking_data.set_solvent_fraction(solvent_fraction)
    tracking_data.set_n_residues(
      n_residues=n_residues_times_ncs)

    return tracking_data
  else:
    return solvent_fraction

def top_key(dd):
  if not dd:
    return None,None
  elif len(dd.keys())==1:
    return dd.keys()[0],dd[dd.keys()[0]]
  else:
    best_key=None
    best_n=None
    for key in dd.keys():
      if not best_n or dd[key] > best_n:
        best_n=dd[key]
        best_key=key
    return best_key,best_n

def choose_max_regions_to_consider(params,
    sorted_by_volume=None,
    ncs_copies=None):

  max_per_au=params.segmentation.max_per_au
  min_ratio=params.segmentation.min_ratio
  min_volume=params.segmentation.min_volume
  # sort and eliminate regions with few points and those at end of list
  if len(sorted_by_volume)<2:
    return 0
  max_grid_points=sorted_by_volume[1][0]
  cntr=0
  for p in sorted_by_volume[1:]:
    cntr+=1
    if max_per_au and (cntr>max_per_au*ncs_copies):
      cntr-=1
      break
    v,i=p  # v=volume in grid points, i=id
    if v/max_grid_points<min_ratio or v < min_volume:
      cntr-=1
      break
  return cntr

def get_edited_mask(sorted_by_volume=None,
    max_regions_to_consider=None,
    co=None,
    out=sys.stdout):
  conn_obj=co.result()
  origin=list(conn_obj.accessor().origin())
  all=list(conn_obj.accessor().all())
  conn_obj.accessor().show_summary(out)
  edited_mask=conn_obj.deep_copy()
  first=True
  edited_volume_list=[]
  original_id_from_id={}
  for i in xrange(1,max_regions_to_consider+1):
    v,id=sorted_by_volume[i]
    original_id_from_id[i]=id
    edited_volume_list.append(v)
    s = (conn_obj==id)
    if first:
      edited_mask=edited_mask.set_selected(~s,0)
      first=False
    edited_mask=edited_mask.set_selected(s,i)   # edited mask has ID of
         # regions, labeled in decreasing size from 1 to max_regions_to_consider
  return edited_mask,edited_volume_list,original_id_from_id

def choose_subset(a,target_number=1):
  new_array=flex.vec3_double()
  assert type(new_array)==type(a)
  n=a.size()
  nskip=max(1,n//target_number)
  i=0
  for x in a:
    if i%nskip==0 or i==n-1:
     new_array.append(x)
    i+=1
  return new_array

def run_get_duplicates_and_ncs(
   ncs_obj=None,
   min_b=None,
   max_b=None,
   edited_mask=None,
   original_id_from_id=None,
   edited_volume_list=None,
   max_regions_to_consider=None,
   regions_left=None,
   tracking_data=None,
   out=sys.stdout,
   ):

  duplicate_dict,equiv_dict,equiv_dict_ncs_copy_dict,region_range_dict,\
     region_centroid_dict,region_scattered_points_dict=\
      get_duplicates_and_ncs(
        ncs_obj=ncs_obj,
        min_b=min_b,
        max_b=max_b,
        edited_mask=edited_mask,
        edited_volume_list=edited_volume_list,
        original_id_from_id=original_id_from_id,
        max_regions_to_consider=max_regions_to_consider,
        tracking_data=tracking_data,
        out=out)

  # check that we have region_centroid for all values
  complete=True
  missing=[]
  for i in xrange(1,max_regions_to_consider+1):
    if not i in region_centroid_dict.keys():
      if (regions_left is None) or (i in regions_left):
         complete=False
         missing.append(i)
  if complete:
       return duplicate_dict,equiv_dict,equiv_dict_ncs_copy_dict,\
        region_range_dict,region_centroid_dict,\
        region_scattered_points_dict
  else:
    raise Sorry("Cannot find region-centroid for all regions? Missing: %s" %(
      missing))

def copy_dict_info(from_dict,to_dict):
  for key in from_dict.keys():
    to_dict[key]=from_dict[key]

def get_centroid_from_blobs(min_b=None,max_b=None,
    id=None,original_id_from_id=None):
  orig_id=original_id_from_id[id]
  upper=max_b[orig_id]
  lower=min_b[orig_id]
  avg=[]
  for u,l in zip(upper,lower):
    avg.append(0.5*(u+l))
  return avg

def get_duplicates_and_ncs(
   ncs_obj=None,
   min_b=None,
   max_b=None,
   edited_mask=None,
   original_id_from_id=None,
   edited_volume_list=None,
   max_regions_to_consider=None,
   target_points_per_region=30,
   minimum_points_per_region=10,
   maximum_points_per_region=100,
   tracking_data=None,
   out=sys.stdout,
   ):

  origin=list(edited_mask.accessor().origin())
  all=list(edited_mask.accessor().all())
  unit_cell=tracking_data.crystal_symmetry.unit_cell()
  # Get sampled points in each region
  sample_dict={}
  region_scattered_points_dict={} # some points in each region
  sampling_rate=edited_volume_list[0]//target_points_per_region
  volumes=flex.int()
  sampling_rates=flex.int()
  id_list=[]
  # have to set up dummy first set:
  volumes.append(0)
  sampling_rates.append(0)
  id_list.append(0)

  for i in xrange(len(edited_volume_list)):
    id=i+1
    v=edited_volume_list[i]

    sample_dict[id]=max(1,
      max(v//maximum_points_per_region,
          min(v//minimum_points_per_region,
              sampling_rate)  ))
    region_scattered_points_dict[id]=flex.vec3_double()

    volumes.append(v)
    sampling_rates.append(max(1,
      max(v//maximum_points_per_region,
          min(v//minimum_points_per_region,
              sampling_rate)  )))
    id_list.append(id)

  sample_regs_obj = maptbx.sample_all_mask_regions(
      mask=edited_mask,
      volumes=volumes,
      sampling_rates=sampling_rates,
      unit_cell=unit_cell)

  for id in id_list[1:]:  # skip the dummy first set
    region_scattered_points_dict[id]=sample_regs_obj.get_array(id)

  # Now just use the scattered points to get everything else:
  region_n_dict={}  # count of points used by region (differs from volume due
     # to the sampling)
  region_range_dict={} # keyed by region in edited_mask; range for x, y, z
  region_centroid_dict={} # keyed by region in edited_mask; range for x, y, z
  for id in region_scattered_points_dict.keys():
    sites=region_scattered_points_dict[id]
    region_n_dict[id]=sites.size()
    if region_n_dict[id]:
      region_centroid_dict[id]=list(sites.mean())
    else: # No points...use bounds from object
      region_centroid_dict[id]=get_centroid_from_blobs(min_b=min_b,
        max_b=max_b,
        id=id,original_id_from_id=original_id_from_id)

  # Now get NCS relationships

  ncs_group=ncs_obj.ncs_groups()[0]
  duplicate_dict={}  # keyed by id, number of duplicates for that region
  equiv_dict={}  # equiv_dict[id][other_id]=number_of points other_id matches
                 #  id through an ncs relationship
  equiv_dict_ncs_copy_dict={}
  for id in region_scattered_points_dict.keys():
    duplicate_dict[id]=0
    equiv_dict[id]={}
    equiv_dict_ncs_copy_dict[id]={}

  # Figure out which ncs operator is the identity
  identity_op=ncs_group.identity_op_id()
  print >>out,"Identity operator is %s" %(identity_op)

  if len(ncs_group.translations_orth())>1:
    # Skip if no ncs...
    for id in region_scattered_points_dict.keys():
      for xyz_cart in region_scattered_points_dict[id]:
        n=0
        for i0 in xrange(len(ncs_group.translations_orth())):
          if i0==identity_op: continue
          r=ncs_group.rota_matrices_inv()[i0] # inverse maps pos 0 on to pos i
          t=ncs_group.translations_orth_inv()[i0]

          n+=1
          new_xyz_cart=r * matrix.col(xyz_cart) + t
          new_xyz_frac=unit_cell.fractionalize(new_xyz_cart)
          value=edited_mask.value_at_closest_grid_point(new_xyz_frac)
          if value==id:
            duplicate_dict[id]+=1
            break # only count once
          elif value>0:  # notice which one is matched
            if not value in equiv_dict[id].keys():
              equiv_dict[id][value]=0
              equiv_dict_ncs_copy_dict[id][value]={}
            equiv_dict[id][value]+=1
            if not n in equiv_dict_ncs_copy_dict[id][value].keys():
              equiv_dict_ncs_copy_dict[id][value][n]=0
            equiv_dict_ncs_copy_dict[id][value][n]+=1  # how many are ncs copy n
  return duplicate_dict,equiv_dict,equiv_dict_ncs_copy_dict,\
      region_range_dict,region_centroid_dict,region_scattered_points_dict

def remove_bad_regions(params=None,
  duplicate_dict=None,
  edited_volume_list=None,
  out=sys.stdout):

  worst_list=[]
  for id in duplicate_dict.keys():
    fract=duplicate_dict[id]/edited_volume_list[id-1]
    if duplicate_dict[id] and fract >=params.segmentation.max_overlap_fraction:
      worst_list.append([fract,id])
    else:
      del duplicate_dict[id]
  worst_list.sort()
  worst_list.reverse()

  bad_region_list=[]
  max_number_to_remove=int(0.5+
    0.01*params.segmentation.remove_bad_regions_percent*len(edited_volume_list))
  if worst_list:
    print >>out,"\nRegions that span multiple NCS au:"
    for fract,id in worst_list:
      print >>out,"ID: %d  Duplicate points: %d (%.1f %%)" %(
        id,duplicate_dict[id],100.*fract),
      if  len(bad_region_list)<max_number_to_remove:
         bad_region_list.append(id)
         print >>out," (removed)"
      else:
         print >>out

  new_sorted_by_volume=[]
  region_list=[]
  region_volume_dict={}
  for i in xrange(len(edited_volume_list)):
    id=i+1
    v=edited_volume_list[i]
    new_sorted_by_volume.append([v,id])
    region_list.append(id)
    region_volume_dict[id]=v
  if bad_region_list:
    print >>out,"Bad regions (excluded)",bad_region_list
  return region_list,region_volume_dict,new_sorted_by_volume,bad_region_list

def sort_by_ncs_overlap(matches,equiv_dict_ncs_copy_dict_id):
    sort_list=[]
    for id1 in matches:
      key,n=top_key(equiv_dict_ncs_copy_dict_id[id1]) # Take top ncs_copy
      sort_list.append([n,id1])
    sort_list.sort()
    sort_list.reverse()
    key_list=[]
    for n,id1 in sort_list:
      key_list.append(id1)
    return key_list


def get_ncs_equivalents(
    bad_region_list=None,
    region_list=None,
    region_scattered_points_dict=None,
    equiv_dict=None,
    ncs_copies=None,
    equiv_dict_ncs_copy_dict=None,
    min_coverage=.10,
    out=sys.stdout):

  equiv_dict_ncs_copy={}
  for id in region_list:
    if id in bad_region_list: continue
    match_dict=equiv_dict.get(id,{}) # which are matches
    matches=match_dict.keys()
    if not matches: continue
    key_list=sort_by_ncs_overlap(matches,equiv_dict_ncs_copy_dict[id])
    n_found=0
    for id1 in key_list:
      #     id matches id1 N=match_dict[id1]

      key,n=top_key(equiv_dict_ncs_copy_dict[id][id1]) # ncs_copy, n-overlap
      if n<min_coverage*region_scattered_points_dict[id].size():
        break
      else:
        if not id in equiv_dict_ncs_copy.keys():equiv_dict_ncs_copy[id]={}
        equiv_dict_ncs_copy[id][id1]=key
        n_found+=1
        if n_found>=ncs_copies-1:
          break

  return equiv_dict_ncs_copy

  # Skipping this below
  print >>out,"\nSets of NCS-related regions"
  keys=equiv_dict_ncs_copy.keys()
  keys.sort()
  used=[]
  for id in keys:
    #if id in used: continue
    others=equiv_dict_ncs_copy[id].keys()
    used+=others
    print >>out,"%d: " %(id),
    for id1 in others:
      key,n=top_key(equiv_dict_ncs_copy_dict[id][id1])
      print >>out,"%d:%d" %(id1,n),
    print >>out
  print >>out

def get_overlap(l1,l2):
  overlap_list=[]
  l1a=single_list(l1)
  l2a=single_list(l2)
  for i in l1a:
    if i in l2a and not i in overlap_list: overlap_list.append(i)
  return overlap_list

def group_ncs_equivalents(params,
    region_list=None,
    region_volume_dict=None,
    equiv_dict_ncs_copy=None,
    tracking_data=None,
    split_if_possible=None,
    out=sys.stdout):

  # equiv_dict_ncs_copy[id][id1]=ncs_copy
  # group together all the regions that are related to region 1...etc
  # if split_if_possible then skip all groups with multiple entries

  ncs_equiv_groups_as_list=[]
  ncs_equiv_groups_as_dict={}
  for id in region_list:
    equiv_group={}  #equiv_group[ncs_copy]=[id1,id2,id3...]
    equiv_group[0]=[id] # always
    for id1 in equiv_dict_ncs_copy.get(id,{}).keys():
      ncs_copy=equiv_dict_ncs_copy[id][id1]
      if not ncs_copy in equiv_group.keys(): equiv_group[ncs_copy]=[]
      equiv_group[ncs_copy].append(id1) # id1 is ncs_copy of id
    all_single=True
    equiv_group_as_list=[]
    total_grid_points=0
    missing_ncs_copies=[]
    present_ncs_copies=[]
    for ncs_copy in xrange(tracking_data.input_ncs_info.number_of_operators):
        # goes 0 to ncs_copies-1 (including extra ones if present)
      local_equiv_group=equiv_group.get(ncs_copy,[])
      if local_equiv_group:
        equiv_group_as_list.append(local_equiv_group)
        present_ncs_copies.append(ncs_copy)
        if ncs_copy > 0 and \
          len(local_equiv_group)>1 and len(equiv_group.get(0,[]))==1:
          all_single=False
        for id in equiv_group.get(ncs_copy,[]):
          total_grid_points+=region_volume_dict[id]
      else:
        missing_ncs_copies.append(ncs_copy)
    equiv_group_as_list.sort()
    if tracking_data.input_ncs_info.is_helical_symmetry:
      # complete if we have original_number_of_operators worth
      if (not params.segmentation.require_complete) or \
         len(present_ncs_copies)>= \
         tracking_data.input_ncs_info.original_number_of_operators:
        complete=True
      else:
        complete=False
    else:
      if len(missing_ncs_copies)==0:
        complete=True
      else:
        complete=False
    if complete and \
        (not str(equiv_group_as_list) in ncs_equiv_groups_as_dict.keys() or
         total_grid_points>ncs_equiv_groups_as_dict[str(equiv_group_as_list)]) \
        and (all_single or (not split_if_possible)):
      ncs_equiv_groups_as_dict[str(equiv_group_as_list)]=total_grid_points
      ncs_equiv_groups_as_list.append([total_grid_points,equiv_group_as_list])

  ncs_equiv_groups_as_list.sort()
  ncs_equiv_groups_as_list.reverse()

  # Now remove any group that duplicates a previous group
  # 2015-11-07 allow a member to be in multiple groups though (for example
  #   one that spans several groups because it contains 2 region in other ncs
  #   copies)
  #  Make sure that if there are duplicates they are all in the leading
  #    positions of the list (these must be very big ones as they match 2
  #    regions in other ncs copies)

  max_duplicates=tracking_data.input_ncs_info.number_of_operators-1 # not all duplicates
  ncs_group_list=[]
  used_list=[]
  print >>out,"All equiv groups:"
  used_regions=[]
  for total_grid_points,equiv_group_as_list in ncs_equiv_groups_as_list:
    duplicate=False
    n_dup=0
    for equiv_group in equiv_group_as_list:
      for x in equiv_group:
        if x in used_list:
          n_dup+=1
    if n_dup>max_duplicates or n_dup >len(equiv_group_as_list)-1:
      duplicate=True
    if not duplicate and n_dup>0:  # check carefully to make sure that all
      # are leading entries
      for ncs_group in ncs_group_list:
        overlaps=get_overlap(ncs_group,equiv_group_as_list)
        if not overlaps: continue
        overlaps.sort()
        expected_match=single_list(equiv_group_as_list)[:len(overlaps)]
        expected_match.sort()
        if overlaps!=expected_match: # not leading entries
          duplicate=True
          break

    if not duplicate:
      #print >>out,"NCS GROUP:",equiv_group_as_list,":",total_grid_points

      ncs_group_list.append(equiv_group_as_list)
      for equiv_group in equiv_group_as_list:
        for x in equiv_group:
          if not x in used_list: used_list.append(x)
  print >>out,"Total NCS groups: %d" %len(ncs_group_list)

  # Make a dict that lists all ids that are in the same group as region x
  shared_group_dict={}
  for ncs_group in ncs_group_list:
    for group_list in ncs_group:
      for id1 in group_list:
        if not id1 in shared_group_dict.keys(): shared_group_dict[id1]=[]
        for other_group_list in ncs_group:
          if other_group_list is group_list:continue
          for other_id1 in other_group_list:
            if not other_id1 in shared_group_dict [id1]:
              shared_group_dict[id1].append(other_id1)

  return ncs_group_list,shared_group_dict

def identify_ncs_regions(params,
     sorted_by_volume=None,
     co=None,
     min_b=None,
     max_b=None,
     ncs_obj=None,
     tracking_data=None,
     out=sys.stdout):

  # 1.choose top regions to work with
  # 2.remove regions that are in more than one au of the NCS
  # 3.identify groups of regions that are related by NCS
  #  Also note the centers and bounds of each region

  # Choose number of top regions to consider

  max_regions_to_consider=choose_max_regions_to_consider(params,
    sorted_by_volume=sorted_by_volume,
    ncs_copies=tracking_data.input_ncs_info.original_number_of_operators)

  print >>out,\
    "\nIdentifying NCS-related regions.Total regions to consider: %d" %(
    max_regions_to_consider)
  if max_regions_to_consider<1:
    print >>out,"\nUnable to identify any NCS regions"
    return None,tracking_data,None

  # Go through all grid points; discard if not in top regions
  #  Renumber regions in order of decreasing size

  load_saved_files=False  # set to True to load results from previous run
  dump_files=False        # set to True to dump results and speed up next run
  if not load_saved_files:
    edited_mask,edited_volume_list,original_id_from_id=get_edited_mask(
     sorted_by_volume=sorted_by_volume,
     co=co,
     max_regions_to_consider=max_regions_to_consider,out=out)
    if dump_files:
      from libtbx import easy_pickle
      easy_pickle.dump("edited_mask.pkl",
        [edited_mask,edited_volume_list,original_id_from_id])
  else:
    from libtbx import easy_pickle
    [edited_mask,edited_volume_list,original_id_from_id
        ]=easy_pickle.load("edited_mask.pkl")
    print >>out,"Loading edited_mask.pkl"

  # edited_mask contains re-numbered region id's

  # Identify duplicate and ncs relationships between regions
  # duplicate_dict[id]= number of duplicates for that region
  # equiv_dict[id][other_id]=number_of points other_id matches
                   #  id through an ncs relationship
  if not load_saved_files:
    duplicate_dict,equiv_dict,equiv_dict_ncs_copy_dict,\
      region_range_dict,region_centroid_dict,\
      region_scattered_points_dict=\
    run_get_duplicates_and_ncs(
      ncs_obj=ncs_obj,
      min_b=min_b,
      max_b=max_b,
      edited_mask=edited_mask,
      original_id_from_id=original_id_from_id,
      edited_volume_list=edited_volume_list,
      max_regions_to_consider=max_regions_to_consider,
      tracking_data=tracking_data,
      out=out)
    # Remove any bad regions
    region_list,region_volume_dict,new_sorted_by_volume,\
      bad_region_list=remove_bad_regions(
    params=params,
    duplicate_dict=duplicate_dict,
    edited_volume_list=edited_volume_list,
    out=out)
    # Identify groups of regions that are ncs-related
    # equiv_dict_ncs_copy[id][id1]=ncs_copy of id that corresponds to id1
    equiv_dict_ncs_copy=get_ncs_equivalents(
    region_list=region_list,
    bad_region_list=bad_region_list,
    region_scattered_points_dict=region_scattered_points_dict,
    equiv_dict=equiv_dict,
    ncs_copies=tracking_data.input_ncs_info.number_of_operators,
    equiv_dict_ncs_copy_dict=equiv_dict_ncs_copy_dict,
    out=out)
    if dump_files:
      from libtbx import easy_pickle
      easy_pickle.dump("save.pkl",[duplicate_dict,equiv_dict,region_range_dict,region_centroid_dict,region_scattered_points_dict,region_list,region_volume_dict,new_sorted_by_volume,bad_region_list,equiv_dict_ncs_copy,tracking_data])
      print >>out,"Dumped save.pkl"
  else:
    from libtbx import easy_pickle
    [duplicate_dict,equiv_dict,region_range_dict,region_centroid_dict,region_scattered_points_dict,region_list,region_volume_dict,new_sorted_by_volume,bad_region_list,equiv_dict_ncs_copy,tracking_data]=easy_pickle.load("save.pkl")
    print >>out,"Loaded save.pkl"

  # Group together regions that are ncs-related. Also if one ncs
  #   copy has 2 or more regions linked together, group the other ones.

  # each entry in ncs_group_list is a list of regions for each ncs_copy:
  #  e.g.,  [[8], [9, 23], [10, 25], [11, 27], [12, 24], [13, 22], [14, 26]]
  #  May contain elements that are in bad_region_list (to exclude later)
  if not load_saved_files:
    ncs_group_list,shared_group_dict=group_ncs_equivalents(params,
    split_if_possible=params.segmentation.split_if_possible,
    tracking_data=tracking_data,
    region_volume_dict=region_volume_dict,
    region_list=region_list,
    equiv_dict_ncs_copy=equiv_dict_ncs_copy,
    out=out)
    if dump_files:
      from libtbx import easy_pickle
      easy_pickle.dump("group_list.pkl",[ncs_group_list,shared_group_dict])
      print >>out,"Dumped to group_list.pkl"
  else:
    from libtbx import easy_pickle
    [ncs_group_list,shared_group_dict]=easy_pickle.load("group_list.pkl")
    print >>out,"Loaded group_list.pkl"

  ncs_group_obj=ncs_group_object(
     ncs_group_list=ncs_group_list,
     shared_group_dict=shared_group_dict,
     ncs_obj=ncs_obj,
     crystal_symmetry=tracking_data.crystal_symmetry,
     edited_mask=edited_mask,
     origin_shift=tracking_data.origin_shift,
     co=co,
     min_b=min_b,
     max_b=max_b,
     equiv_dict=equiv_dict,
     bad_region_list=bad_region_list,
     original_id_from_id=original_id_from_id,
     edited_volume_list=edited_volume_list,
     region_range_dict=region_range_dict,
     region_scattered_points_dict=region_scattered_points_dict,
     region_centroid_dict=region_centroid_dict)

  return ncs_group_obj,tracking_data,equiv_dict_ncs_copy

def get_center_list(regions,
    region_centroid_dict=None):
  center_list=[]
  for region in regions:
    center_list.append(region_centroid_dict[region])
  return center_list

def get_average_center(regions,
    region_centroid_dict=None):
  center_list=get_center_list(regions,region_centroid_dict=region_centroid_dict)
  for region in regions:
    center_list.append(region_centroid_dict[region])
  average_center=deepcopy(center_list[0])
  if len(center_list)>1:
    for r in center_list[1:]:
      for i in xrange(3):
        average_center[i]+=r[i]
    for i in xrange(3):
      average_center[i]/=len(center_list)
  return average_center

def get_dist(r,s):
  dd=0.
  for i in xrange(3):
    dd+=(r[i]-s[i])**2
  return dd**0.5

def has_intersection(set1,set2):
  set1a=single_list(set1)
  set2a=single_list(set2)
  for x in set1a:
    if x in set2a:
      return True
  return False

def get_scattered_points_list(other_regions,
       region_scattered_points_dict=None):
  scattered_points_list=flex.vec3_double()
  for x in other_regions:
    scattered_points_list.extend(region_scattered_points_dict[x])
  return scattered_points_list

def get_inter_region_dist_dict(ncs_group_obj=None,
    selected_regions=None,target_scattered_points=None):
  dd={}
  for i in xrange(len(selected_regions)):
    id=selected_regions[i]
    if not id in dd.keys(): dd[id]={}
    test_centers=ncs_group_obj.region_scattered_points_dict[id]
    for j in xrange(i+1,len(selected_regions)):
      id1=selected_regions[j]
      test_centers1=ncs_group_obj.region_scattered_points_dict[id1]
      dist=get_closest_dist(test_centers,test_centers1)
      dd[id][id1]=dist
      if not id1 in dd.keys(): dd[id1]={}
      dd[id1][id]=dist
  return dd

def get_dist_to_first_dict(ncs_group_obj=None,
     selected_regions=None,
     inter_region_dist_dict=None,
     target_scattered_points=None):

  # Get distance to region 0 ( or to target_scattered_points if supplied)
  dist_to_first_dict={}
  if target_scattered_points:
    start_region=0
    for x in selected_regions:
      dist_to_first_dict[x]=get_closest_dist(
        ncs_group_obj.region_scattered_points_dict[x],
        target_scattered_points)
  else:
    start_region=1
    x0=selected_regions[0]
    dist_to_first_dict[x0]=0
    for x in selected_regions[1:]:
      dist_to_first_dict[x]=inter_region_dist_dict[x0][x]
  changing=True
  while changing:
    changing=False
    for x in selected_regions[start_region:]:
      for y in selected_regions[start_region:]:
        if x==y: continue
        if dist_to_first_dict[y]<dist_to_first_dict[x] and \
            inter_region_dist_dict[x][y]<dist_to_first_dict[x]:
          dist_to_first_dict[x]=max(
            dist_to_first_dict[y],inter_region_dist_dict[x][y])
          changing=True
  return dist_to_first_dict

def get_radius_of_gyration(ncs_group_obj=None,
    selected_regions=None):
  # return radius of gyration of points in selected regions
  centers=flex.vec3_double()
  for s in selected_regions:
    centers.append(ncs_group_obj.region_centroid_dict[s])
  centers=centers-centers.mean()
  return centers.rms_length()


def get_closest_neighbor_rms(ncs_group_obj=None,selected_regions=None,
    target_scattered_points=None,verbose=False,out=sys.stdout):

  # return rms closest distance of each region center to lowest_numbered region,
  #   allowing sequential tracking taking max of inter-region distances

  # XXX can't we save some of this for next time?

  inter_region_dist_dict=get_inter_region_dist_dict(ncs_group_obj=ncs_group_obj,
     selected_regions=selected_regions)
  if verbose:
    print >>out,"Inter-region distance dict:"
    keys=inter_region_dist_dict.keys()
    keys.sort()
    for key in keys:
      for key2 in inter_region_dist_dict[key].keys():
        print >>out,"%s  %s  : %.1f " %(key,key2,inter_region_dist_dict[key][key2])

  dist_to_first_dict=get_dist_to_first_dict(ncs_group_obj=ncs_group_obj,
     selected_regions=selected_regions,
     inter_region_dist_dict=inter_region_dist_dict,
     target_scattered_points=target_scattered_points)

  if verbose:
    print >>out,"Distance-to-first dict:"
    keys=dist_to_first_dict.keys()
    keys.sort()
    for key in keys: print >>out,"\n %s:  %.1f " %(key,dist_to_first_dict[key])

  if target_scattered_points:
    start_region=0 # we are getting dist to target_scattered_points
  else:
    start_region=1 # we are getting dist to region 0

  rms=0.
  rms_n=0.
  for x in selected_regions[start_region:]:
    dist=dist_to_first_dict[x]
    rms+=dist**2
    rms_n+=1.
  if rms_n>1:
    rms/=rms_n
  rms=rms**0.5
  return rms


def get_rms(selected_regions=None,
    region_centroid_dict=None):
  # return rms distance of each region center from average of all others
  rms=0.
  rms_n=0.
  for x in selected_regions:
    other_regions=remove_one_item(selected_regions,item_to_remove=x)
    current_center=get_average_center(other_regions,
       region_centroid_dict=region_centroid_dict)
    test_center=region_centroid_dict[x]
    dist=get_dist(current_center,test_center)
    rms+=dist**2
    rms_n+=1.
  if rms_n>1:
    rms/=rms_n
  return rms**0.5

def single_list(list_of_lists):
  single=[]
  for x in list_of_lists:
    if type(x)==type([1,2,3]):
      single+=single_list(x)
    else:
      single.append(x)
  return single

def get_closest_dist(test_center,target_centers):
  # make sure we have target_centers=vec3_double and not a list,
  #  and vec3_double or tuple for test_center

  if type(test_center)==type([1,2,3]):
    test_center=flex.vec3_double(test_center)
  if type(target_centers)==type([1,2,3]):
    target_centers=flex.vec3_double(target_centers)
  if test_center.size()<1 or target_centers.size()<1: return None
  closest_dist=test_center.min_distance_between_any_pair(target_centers)
  return closest_dist

def region_lists_have_ncs_overlap(set1,set2,ncs_group_obj=None,cutoff=0):
  for id1 in set1:
    for id2 in set2:
      if id2 in ncs_group_obj.shared_group_dict.get(id1,[]):
        return True
  return False

def get_effective_radius(ncs_group_obj=None,
    target_scattered_points=None,
    weight_rad_gyr=None,
    selected_regions=None):
  sr=deepcopy(selected_regions)
  sr.sort()
  rad_gyr=get_radius_of_gyration(ncs_group_obj=ncs_group_obj,
     selected_regions=sr)
  rms=get_closest_neighbor_rms(ncs_group_obj=ncs_group_obj,
    target_scattered_points=target_scattered_points,
    selected_regions=sr)
  max_cell_dim=0.
  if ncs_group_obj.max_cell_dim and ncs_group_obj.max_cell_dim > 1.0:
    wrg=weight_rad_gyr*(300/ncs_group_obj.max_cell_dim)  # have a consistent scale
  else:
    wrg=weight_rad_gyr
  effective_radius=(rms+wrg*rad_gyr)/(1.+wrg)
  return effective_radius

def add_neighbors(params,
      selected_regions=None,
      max_length_of_group=None,
      target_scattered_points=None,
      tracking_data=None,
      equiv_dict_ncs_copy=None,
      ncs_group_obj=None,out=sys.stdout):

  #   Add neighboring regions on to selected_regions. 
  #   Same rules as select_from_seed

  selected_regions=single_list(deepcopy(selected_regions))

  added_regions=[]
  start_dist=get_effective_radius(ncs_group_obj=ncs_group_obj,
        target_scattered_points=target_scattered_points,
        weight_rad_gyr=params.segmentation.weight_rad_gyr,
        selected_regions=selected_regions)
  delta_dist=params.segmentation.add_neighbors_dist
  max_dist=start_dist+delta_dist

  starting_selected_regions=deepcopy(selected_regions)

  for x in selected_regions:  # delete, add in alternatives one at a time and
    #  keep all the ok ones
    ncs_groups_to_use=get_ncs_related_regions(
      ncs_group_obj=ncs_group_obj,
      selected_regions=[x],
      include_self=False)

    for x in ncs_groups_to_use: # try adding from each group
      if x in selected_regions+added_regions:
        continue
      ncs_group=[[x]]
      current_scattered_points_list=get_scattered_points_list(selected_regions,
        region_scattered_points_dict=ncs_group_obj.region_scattered_points_dict)

      for ncs_set in ncs_group: # pick the best ncs_set from this group
        if has_intersection(ncs_group_obj.bad_region_list,ncs_set): 
          continue

        dist=get_effective_radius(ncs_group_obj=ncs_group_obj,
          target_scattered_points=target_scattered_points,
          weight_rad_gyr=params.segmentation.weight_rad_gyr,
          selected_regions=selected_regions+ncs_set)

        if dist <= max_dist:
          added_regions.append(x)

  selected_regions=selected_regions+added_regions
  dist=get_effective_radius(ncs_group_obj=ncs_group_obj,
          target_scattered_points=target_scattered_points,
          weight_rad_gyr=params.segmentation.weight_rad_gyr,
          selected_regions=selected_regions)

  # Identify all the NCS operators required to map final to starting
  # equiv_dict_ncs_copy[id][id1]=ncs_copy of id that corresponds to id1
  ncs_group=ncs_group_obj.ncs_obj.ncs_groups()[0]
  identity_op=ncs_group.identity_op_id()
  ncs_ops_used=[identity_op]
  
  did_not_find_list=[]
  for id in selected_regions:
    related_regions=get_ncs_related_regions(
      ncs_group_obj=ncs_group_obj,
      selected_regions=[id],
      include_self=False)
    for id1 in selected_regions:
      if not id1 in related_regions: continue 
      ncs_copy1=equiv_dict_ncs_copy.get(id,{}).get(id1,None)
      ncs_copy2=equiv_dict_ncs_copy.get(id1,{}).get(id,None)
      for a in [ncs_copy1,ncs_copy2]:
        if a is None:
          x=[id,id1]
          x.sort()
          x="%s_%s" %(tuple(x))
          if not x in did_not_find_list: 
            did_not_find_list.append(x)
        else:
          if not a in ncs_ops_used:
            ncs_ops_used.append(a)
  selected_regions.sort()
  ncs_ops_used.sort()
  for x in selected_regions:
    print >>out,"GROUP ",x,":",ncs_group_obj.shared_group_dict.get(x,[])

  return selected_regions,dist,ncs_ops_used

def select_from_seed(params,
      starting_regions,
      target_scattered_points=None,
      max_length_of_group=None,
      ncs_groups_to_use=None,
      tracking_data=None,
      ncs_group_obj=None):
  selected_regions=single_list(deepcopy(starting_regions))
  # do not allow any region in ncs_group_obj.bad_region_list
  # also do not allow any region that is in an ncs-related group to any region
  #  already used.  Use ncs_group_obj.equiv_dict to identify these.
  if not ncs_groups_to_use:
    ncs_groups_to_use=ncs_group_obj.ncs_group_list

  for ncs_group in ncs_groups_to_use: # try adding from each group
    if max_length_of_group is not None and \
       len(selected_regions)>=max_length_of_group:
      break
    best_ncs_set=None
    best_dist=None
    if has_intersection(ncs_group,selected_regions):
      continue
    current_scattered_points_list=get_scattered_points_list(selected_regions,
       region_scattered_points_dict=ncs_group_obj.region_scattered_points_dict)
    if target_scattered_points:
      current_scattered_points_list.extend(target_scattered_points)

    for ncs_set in ncs_group: # pick the best ncs_set from this group
      if has_intersection(ncs_group_obj.bad_region_list,ncs_set): continue

      # does any ncs copy of anything in selected_regions actually overlap
      #  with any member of ncs_set... might be efficient to delete the entire
      #   ncs_group if any ncs_set overlaps, but could lose some.
      if region_lists_have_ncs_overlap(ncs_set,selected_regions,
          ncs_group_obj=ncs_group_obj):
        continue

      dist=get_effective_radius(ncs_group_obj=ncs_group_obj,
        target_scattered_points=target_scattered_points,
        weight_rad_gyr=params.segmentation.weight_rad_gyr,
        selected_regions=selected_regions+ncs_set)

      if best_dist is None or dist<best_dist:
        best_dist=dist
        best_ncs_set=ncs_set
    if best_ncs_set is not None:
      selected_regions+=best_ncs_set

  dist=get_effective_radius(ncs_group_obj=ncs_group_obj,
    target_scattered_points=target_scattered_points,
    weight_rad_gyr=params.segmentation.weight_rad_gyr,
    selected_regions=selected_regions)

  return selected_regions,dist

def remove_one_item(input_list,item_to_remove=None):
  new_list=[]
  for item in input_list:
    if item != item_to_remove:
      new_list.append(item)
  return new_list


def get_ncs_related_regions_specific_list(
    ncs_group_obj=None,
    target_regions=None,
    include_self=False):
  all_regions=[]
  for target_region in target_regions:
    all_regions+=get_ncs_related_regions_specific_target(
      ncs_group_obj=ncs_group_obj,
      target_region=target_region,
      other_regions=remove_one_item(
         target_regions,item_to_remove=target_region),
      include_self=include_self)
  return all_regions

def get_ncs_related_regions_specific_target(
          ncs_group_obj=None,
          target_region=None,
          other_regions=None,
          include_self=False):
  # similar to get_ncs_related_regions, but find just one  ncs group that
  #  contains x but does not contain any member of other_regions
  for ncs_group in ncs_group_obj.ncs_group_list: # might this be the group
    ids_in_group=single_list(ncs_group)
    if not target_region in ids_in_group: continue # does not contain target
    contains_others=False
    for other_id in other_regions:
      if other_id in ids_in_group:
        contains_other=True
        break# contains other members
    if not contains_others:
      # this is the group
      if include_self:
        return ids_in_group
      else:
        return remove_one_item(ids_in_group,item_to_remove=target_region)
  return []


def get_ncs_related_regions(
    ncs_group_obj=None,
    selected_regions=None,
    include_self=False):
  # returns a simple list of region ids
  # if include_self then include selected regions and all ncs-related
  #   otherwise do not include selected regions or anything that might
  #   overlap with them

  ncs_related_regions=[]
  if include_self:
    for id in selected_regions:
      if not id in ncs_related_regions:
        ncs_related_regions.append(id)
      for ncs_group in ncs_group_obj.ncs_group_list:
        ids_in_group=single_list(ncs_group)
        if id in ids_in_group:  # this group contains this selected id
          for i in ids_in_group:
            if not i in ncs_related_regions:
              ncs_related_regions.append(i)

  else:
    for id in selected_regions:
      found=False
      for ncs_group in ncs_group_obj.ncs_group_list:
        ids_in_group=single_list(ncs_group)
        if id in ids_in_group:  # this group contains this selected id
          found=True
          for i in ids_in_group:
            if (not i==id) and (not i in selected_regions) and \
               (not i in ncs_related_regions):
              ncs_related_regions.append(i)
          break # don't look at any more ncs groups

  return ncs_related_regions

def all_elements_are_length_one(list_of_elements):
  for x in list_of_elements:
    if type(x)==type([1,2,3]):
      if len(x)!=1: return False
  return True

def as_list_of_lists(ll):
  new_list=[]
  for x in ll:
    new_list.append([x])
  return new_list

def select_regions_in_au(params,
     ncs_group_obj=None,
     target_scattered_points=None,
     unique_expected_regions=None,
     equiv_dict_ncs_copy=None,
     tracking_data=None,
     out=sys.stdout):
  # Choose one region or set of regions from each ncs_group
  # up to about unique_expected_regions
  # Optimize closeness of centers...
  # If target scattered_points is supplied, include them as allowed target

  if not ncs_group_obj.ncs_group_list:
    return ncs_group_obj,[]

  max_length_of_group=max(1,unique_expected_regions*
     params.segmentation.max_per_au_ratio)
  print >>out,"Maximum length of group: %d" %(max_length_of_group)

  if all_elements_are_length_one(ncs_group_obj.ncs_group_list):
    # This is where there is no ncs. Basically skipping everything
    best_selected_regions=single_list(ncs_group_obj.ncs_group_list)
    best_rms=None
  else:
    #--------------  Find initial set of regions --------------------
    # Seed with members of the first NCS group or with the target points
    #  and find the member of each NCS group that is closest

    if target_scattered_points:
      starting_regions=[None]
    else:
      starting_regions=ncs_group_obj.ncs_group_list[0]

    best_selected_regions=None
    best_rms=None
    ok_seeds_examined=0
    for starting_region in starting_regions: # NOTE starting_region is a list
      if not starting_region and not target_scattered_points:continue
      if ok_seeds_examined >= params.segmentation.seeds_to_try:
        break # don't bother to keep trying
      if starting_region and starting_region in ncs_group_obj.bad_region_list:
        continue # do not use
      if starting_region: # NOTE: starting_region is a list itself
        starting_region_list=[starting_region]
      else:
        starting_region_list=[]
      selected_regions,rms=select_from_seed(params,
        starting_region_list,
        target_scattered_points=target_scattered_points,
        max_length_of_group=max_length_of_group,
        tracking_data=tracking_data,
        ncs_group_obj=ncs_group_obj)
      if not selected_regions:
        continue
      ok_seeds_examined+=1
      if best_rms is None or rms<best_rms:
        best_rms=rms
        best_selected_regions=selected_regions
        print >>out,"New best selected: rms: %7.1f: %s " %(
           rms,str(selected_regions))

    if best_rms is not None:
      print >>out,"Best selected so far: rms: %7.1f: %s " %(
            best_rms,str(best_selected_regions))

    if not best_selected_regions:
      print >>out, "\nNo NCS regions found ..."
      return ncs_group_obj,[]

    # Now we have a first version of best_rms, best_selected_regions

    #--------------  END Find initial set of regions --------------------


    #--------------  Optimize choice of regions -------------------------
    max_tries=10
    improving=True
    itry=0
    while improving and itry<max_tries:
      itry+=1
      improving=False
      previous_selected_regions=deepcopy(best_selected_regions)
      previous_selected_regions.sort()
      print >>out,"\nTry %d for optimizing regions" %(itry)
      # Now see if replacing any regions with alternatives would improve it
      for x in previous_selected_regions:
        starting_regions=remove_one_item(previous_selected_regions,
          item_to_remove=x)
        # identify ncs_related regions to x, but not to other members of
        #  selected_regions
        ncs_related_regions=get_ncs_related_regions_specific_list(
          ncs_group_obj=ncs_group_obj,
          include_self=True,
          target_regions=[x])
        if not ncs_related_regions: continue
        ncs_groups_to_use=[as_list_of_lists(ncs_related_regions)]
        new_selected_regions,rms=select_from_seed(params,starting_regions,
          target_scattered_points=target_scattered_points,
          max_length_of_group=max_length_of_group,
          tracking_data=tracking_data,
          ncs_groups_to_use=ncs_groups_to_use,
          ncs_group_obj=ncs_group_obj)

        if not new_selected_regions: continue
        if best_rms is None or rms<best_rms:
          best_selected_regions=new_selected_regions
          best_selected_regions.sort()
          best_rms=rms
          improving=True
      print >>out,"Optimized best selected: rms: %7.1f: %s " %(
          best_rms,str(best_selected_regions))

      # Done with this try

  selected_regions=best_selected_regions
  selected_regions.sort()

  rms=get_closest_neighbor_rms(ncs_group_obj=ncs_group_obj,
    selected_regions=selected_regions,verbose=False,out=out)

  if params.segmentation.add_neighbors and \
       ncs_group_obj.ncs_obj.max_operators()>1:
    print >>out,"\nAdding neighbor groups..."
    selected_regions,rms,ncs_ops_used=add_neighbors(params,
          selected_regions=selected_regions,
          max_length_of_group=max_length_of_group,
          target_scattered_points=target_scattered_points,
          equiv_dict_ncs_copy=equiv_dict_ncs_copy,
          tracking_data=tracking_data,
          ncs_group_obj=ncs_group_obj,out=out)
  else:
    ncs_ops_used=None

  print >>out,"\nFinal selected regions with rms of %6.2f: " %(rms),
  for x in selected_regions:
    print >>out,x,
  if ncs_ops_used:
    print >>out,"\nNCS operators used: ",
    for op in ncs_ops_used:  print >>out, op,
    print >>out
  # Save an ncs object containing just the ncs_ops_used
  ncs_group_obj.set_ncs_ops_used(ncs_ops_used)

  # Identify scattered points for all selected regions:

  scattered_points=get_scattered_points_list(selected_regions,
     region_scattered_points_dict=ncs_group_obj.region_scattered_points_dict)

  # Identify ncs-related regions for all the selected regions
  self_and_ncs_related_regions=get_ncs_related_regions(
    ncs_group_obj=ncs_group_obj,
    selected_regions=selected_regions,
    include_self=True)

  ncs_related_regions=get_ncs_related_regions(
    ncs_group_obj=ncs_group_obj,
    selected_regions=selected_regions,
    include_self=False)

  print >>out,"NCS-related regions (not used): %d " %(len(ncs_related_regions))
  ncs_group_obj.set_selected_regions(selected_regions)
  ncs_group_obj.set_self_and_ncs_related_regions(self_and_ncs_related_regions)
  ncs_group_obj.set_ncs_related_regions(ncs_related_regions)

  return ncs_group_obj,scattered_points

def get_bool_mask_as_int(ncs_group_obj=None,mask_as_int=None,mask_as_bool=None):
  if mask_as_int:
    mask_as_int=mask_as_int.deep_copy()
  else:
    mask_as_int=ncs_group_obj.edited_mask.deep_copy()
  s = (mask_as_bool==True)
  mask_as_int = mask_as_int.set_selected(s,1)
  mask_as_int = mask_as_int.set_selected(~s,0)
  return mask_as_int

def get_bool_mask_of_regions(ncs_group_obj=None,region_list=None,
    expand_size=None):
  s = (ncs_group_obj.edited_mask == -1)
  if region_list is None: region_list=[]
  for id in region_list:

    if not expand_size:
      s |= (ncs_group_obj.edited_mask==id)  # just take this region

    else:  # expand the size of the regions...use expand_mask which operates
         # on the original id numbers and uses the co
      bool_region_mask = ncs_group_obj.co.expand_mask(
        id_to_expand=ncs_group_obj.original_id_from_id[id],
        expand_size=expand_size)
      s |= (bool_region_mask== True)

  bool_mask = ncs_group_obj.co.expand_mask(id_to_expand=1,expand_size=1) # just to get bool mask
  bool_mask = bool_mask.set_selected(s,True)
  bool_mask = bool_mask.set_selected(~s,False)

  return bool_mask

def create_remaining_mask_and_map(params,
    ncs_group_obj=None,
    map_data=None,
    crystal_symmetry=None,
    out=sys.stdout):

  if not ncs_group_obj.selected_regions:
    print >>out,"No regions selected"
    return map_data

  # create new remaining_map containing everything except the part that
  # has been interpreted (and all points in interpreted NCS-related copies)

  bool_all_used=get_bool_mask_of_regions(ncs_group_obj=ncs_group_obj,
   region_list=ncs_group_obj.selected_regions+
       ncs_group_obj.self_and_ncs_related_regions,
   expand_size=params.segmentation.expand_size)
  map_data_remaining=map_data.deep_copy()
  s=(bool_all_used==True)

  map_data_remaining=map_data_remaining.set_selected(s,
    params.segmentation.value_outside_mask)
  return map_data_remaining

def get_lower(lower_bounds,lower):
  new_lower=[]
  for i in xrange(3):
    if lower_bounds[i] is None:
      new_lower.append(lower[i])
    elif lower[i] is None:
      new_lower.append(lower_bounds[i])
    else:
      new_lower.append(min(lower_bounds[i],lower[i]))
  return new_lower

def get_upper(upper_bounds,upper):
  new_upper=[]
  for i in xrange(3):
    if upper_bounds[i] is None:
      new_upper.append(upper[i])
    elif upper[i] is None:
      new_upper.append(upper_bounds[i])
    else:
      new_upper.append(max(upper_bounds[i],upper[i]))
  return new_upper

def get_bounds(ncs_group_obj=None,id=None):
  orig_id=ncs_group_obj.original_id_from_id[id]
  lower=ncs_group_obj.min_b[orig_id]
  upper=ncs_group_obj.max_b[orig_id]
  return lower,upper

def get_selected_and_related_regions(params,
    ncs_group_obj=None):
  # Identify all points in the targeted regions
  bool_selected_regions=get_bool_mask_of_regions(ncs_group_obj=ncs_group_obj,
     region_list=ncs_group_obj.selected_regions,
     expand_size=params.segmentation.expand_size+\
      params.segmentation.mask_additional_expand_size)
  # and all points in NCS-related copies (to be excluded)
  if params.segmentation.exclude_points_in_ncs_copies and (
     not params.segmentation.add_neighbors):
    bool_ncs_related_mask=get_bool_mask_of_regions(ncs_group_obj=ncs_group_obj,
       region_list=ncs_group_obj.ncs_related_regions)
     # NOTE: using ncs_related_regions here NOT self_and_ncs_related_regions
  else:
    bool_ncs_related_mask=None

  lower_bounds=[None,None,None]
  upper_bounds=[None,None,None]
  if ncs_group_obj.selected_regions:
    for id in ncs_group_obj.selected_regions:
      lower,upper=get_bounds(
        ncs_group_obj=ncs_group_obj,id=id)
      lower_bounds=get_lower(lower_bounds,lower)
      upper_bounds=get_upper(upper_bounds,upper)

  return bool_selected_regions,bool_ncs_related_mask,lower_bounds,upper_bounds

def adjust_bounds(params,
   lower_bounds,upper_bounds,map_data=None,out=sys.stdout):
  # range is lower_bounds to upper_bounds
  lower_bounds=list(lower_bounds)
  upper_bounds=list(upper_bounds)
  if params.output_files.box_buffer is None: params.output_files.box_buffer=0
  for i in xrange(3):
    if lower_bounds[i] is None: lower_bounds[i]=0
    if upper_bounds[i] is None: upper_bounds[i]=0
    lower_bounds[i]-=params.output_files.box_buffer
    lower_bounds[i]=max(0,lower_bounds[i])
    upper_bounds[i]+=params.output_files.box_buffer
    upper_bounds[i]=min(map_data.all()[i]-1,upper_bounds[i])


  """
  print >>out,"\nRange:  X:(%6d,%6d)    Y:(%6d,%6d)    Z:(%6d,%6d)" %(
     lower_bounds[0],upper_bounds[0],
     lower_bounds[1],upper_bounds[1],
     lower_bounds[2],upper_bounds[2])
  """

  return lower_bounds,upper_bounds

def write_region_maps(params,
    ncs_group_obj=None,
    map_data=None,
    tracking_data=None,
    remainder_ncs_group_obj=None,
    regions_to_skip=None,
    out=sys.stdout):
  remainder_regions_written=[]
  map_files_written=[]
  if not ncs_group_obj:
    return map_files_written,remainder_regions_written

  if not ncs_group_obj.selected_regions:
    return map_files_written,remainder_regions_written

  for id in ncs_group_obj.selected_regions:


    if regions_to_skip and id in regions_to_skip:
      print >>out,"Skipping remainder region %d (already written out)" %(id)
      continue
    print >>out,"Writing region %d" %(id),

    # dummy atoms representing this region
    sites=ncs_group_obj.region_scattered_points_dict[id]

    bool_region_mask = ncs_group_obj.co.expand_mask(
        id_to_expand=ncs_group_obj.original_id_from_id[id],
        expand_size=params.segmentation.expand_size)

    s = (bool_region_mask==True)

    lower_bounds,upper_bounds=get_bounds(ncs_group_obj=ncs_group_obj,id=id)

    if remainder_ncs_group_obj:
      for remainder_id in remainder_ncs_group_obj.remainder_id_dict.keys():
        if remainder_ncs_group_obj.remainder_id_dict[remainder_id]==id:
          remainder_regions_written.append(remainder_id)

          sites.extend(
            remainder_ncs_group_obj.region_scattered_points_dict[remainder_id])

          print >>out,"(including remainder region %d)" %(remainder_id),
          remainder_bool_region_mask = remainder_ncs_group_obj.co.expand_mask(
           id_to_expand=remainder_ncs_group_obj.original_id_from_id[remainder_id],
           expand_size=params.segmentation.expand_size)
          s|= (remainder_bool_region_mask==True)
          lower,upper=get_bounds(
            ncs_group_obj=remainder_ncs_group_obj,id=remainder_id)
          lower_bounds=get_lower(lower_bounds,lower)
          upper_bounds=get_upper(upper_bounds,upper)


    region_mask = map_data.deep_copy()
    region_mask = region_mask.set_selected(s,1)
    region_mask = region_mask.set_selected(~s,0)
    local_map_data=map_data.deep_copy()
    local_map_data=local_map_data * region_mask.as_double()

    # Now cut down the map to the size we want
    lower_bounds,upper_bounds=adjust_bounds(params,lower_bounds,upper_bounds,
      map_data=map_data,out=out)
    box_map,box_crystal_symmetry=cut_out_map(
       map_data=local_map_data, crystal_symmetry=tracking_data.crystal_symmetry,
       min_point=lower_bounds, max_point=upper_bounds,out=out)

    if remainder_ncs_group_obj:
      text=""
    else:
      text="_r"
    base_file='map%s_%d.ccp4' %(text, id)
    base_pdb_file='atoms%s_%d.pdb' %(text, id)
    if tracking_data.params.output_files.output_directory:
      if not os.path.isdir(tracking_data.params.output_files.output_directory):
        os.mkdir(tracking_data.params.output_files.output_directory)
      file_name=os.path.join(tracking_data.params.output_files.output_directory,base_file)
      pdb_file_name=os.path.join(
        tracking_data.params.output_files.output_directory,base_pdb_file)
    else:
      file_name=base_file
      pdb_file_name=base_pdb_file
    write_ccp4_map(box_crystal_symmetry,file_name, box_map)
    print >>out,"to %s" %(file_name)
    map_files_written.append(file_name)

    tracking_data.add_output_region_map_info(
      file_name=file_name,
      crystal_symmetry=box_crystal_symmetry,
      origin=box_map.origin(),
      all=box_map.all(),
      map_id=base_file)

    print >>out,"Atoms representation written to %s" %(pdb_file_name)
    write_atoms(tracking_data=tracking_data,sites=sites,file_name=pdb_file_name,
       out=out)
    tracking_data.add_output_region_pdb_info(
      file_name=pdb_file_name)

  return map_files_written,remainder_regions_written

def get_bounds_from_sites(sites_cart=None,map_data=None,
    unit_cell=None):
  lower_bounds=[None,None,None]
  upper_bounds=[None,None,None]
  sites_frac=unit_cell.fractionalize(sites_cart)
  nx,ny,nz=map_data.all()
  for x_frac in sites_frac:
    x=[
      int(0.5+nx*x_frac[0]),
      int(0.5+ny*x_frac[1]),
      int(0.5+nz*x_frac[2])]

    if lower_bounds[0] is None or x[0]<lower_bounds[0]: lower_bounds[0]=x[0]
    if lower_bounds[1] is None or x[1]<lower_bounds[1]: lower_bounds[1]=x[1]
    if lower_bounds[2] is None or x[2]<lower_bounds[2]: lower_bounds[2]=x[2]

    if upper_bounds[0] is None or x[0]>upper_bounds[0]: upper_bounds[0]=x[0]
    if upper_bounds[1] is None or x[1]>upper_bounds[1]: upper_bounds[1]=x[1]
    if upper_bounds[2] is None or x[2]>upper_bounds[2]: upper_bounds[2]=x[2]
  return lower_bounds,upper_bounds

def write_output_files(params,
    tracking_data=None,
    map_data=None,
    ncs_group_obj=None,
    remainder_ncs_group_obj=None,
    pdb_hierarchy=None,
    removed_ncs=None,
    out=sys.stdout):

  if params.output_files.au_output_file_stem:
    au_mask_output_file=os.path.join(tracking_data.params.output_files.output_directory,params.output_files.au_output_file_stem+"_mask.ccp4")
    au_map_output_file=os.path.join(tracking_data.params.output_files.output_directory,params.output_files.au_output_file_stem+"_map.ccp4")
    au_atom_output_file=os.path.join(tracking_data.params.output_files.output_directory,params.output_files.au_output_file_stem+"_atoms.pdb")
  else:
    au_mask_output_file=None
    au_map_output_file=None
    au_atom_output_file=None

  # Write out pdb file with dummy atoms for the AU to au_atom_output_file
  if au_atom_output_file:
    sites=flex.vec3_double()
    for id in ncs_group_obj.selected_regions:
      sites.extend(ncs_group_obj.region_scattered_points_dict[id])
    if remainder_ncs_group_obj:
      for id in remainder_ncs_group_obj.selected_regions:
        sites.extend(remainder_ncs_group_obj.region_scattered_points_dict[id])
    write_atoms(tracking_data=tracking_data,sites=sites,
      file_name=au_atom_output_file,out=out)
    tracking_data.set_output_ncs_au_pdb_info(file_name=au_atom_output_file)


  # Write out mask and map representing one NCS copy and none of
  #   other NCS copies.  Expand the mask to include neighboring points (but
  #   not those explicitly in other NCS copies

  bool_selected_regions,bool_ncs_related_mask,lower_bounds,upper_bounds=\
     get_selected_and_related_regions(
      params,ncs_group_obj=ncs_group_obj)
  if bool_ncs_related_mask is not None:
    s_ncs_related =  (bool_ncs_related_mask==True)
  else:
    s_ncs_related =  None

  # Add in remainder regions if present
  if remainder_ncs_group_obj:
    bool_remainder_selected_regions,bool_remainder_ncs_related_mask,\
      remainder_lower_bounds,remainder_upper_bounds=\
       get_selected_and_related_regions(
       params,ncs_group_obj=remainder_ncs_group_obj)

    lower_bounds=get_lower(lower_bounds,remainder_lower_bounds)
    upper_bounds=get_upper(upper_bounds,remainder_upper_bounds)

    s_remainder_au =  (bool_remainder_selected_regions==True)
    bool_selected_regions=bool_selected_regions.set_selected(
       s_remainder_au,True)
    if s_ncs_related is not None and \
         bool_remainder_ncs_related_mask is not None:
      s_ncs_related |=  (bool_remainder_ncs_related_mask==True)

  # Now create NCS mask by eliminating all points in target (expanded) in
  #   NCS-related copies
  if s_ncs_related is not None:
    bool_selected_regions=bool_selected_regions.set_selected(
       s_ncs_related,False)

  # Identify full (possibly expanded) ncs au starting with what we have
  au_mask=get_one_au(tracking_data=tracking_data,
    starting_mask=bool_selected_regions,
    removed_ncs=removed_ncs,
    ncs_obj=ncs_group_obj.ncs_obj,map_data=map_data,out=out)

  print >>out,"\nExpanding NCS AU if necessary..."
  print >>out,"Size of AU mask: %s  Current size of AU: %s" %(
    au_mask.count(True),bool_selected_regions.count(True))
  bool_selected_regions=(bool_selected_regions | au_mask)
  print >>out,"New size of AU mask: %s" %(bool_selected_regions.count(True))

  sites_cart=get_marked_points_cart(mask_data=bool_selected_regions,
     unit_cell=ncs_group_obj.crystal_symmetry.unit_cell(),
     every_nth_point=tracking_data.params.segmentation.grid_spacing_for_au,
     boundary_radius=tracking_data.params.segmentation.radius)
  sites_lower_bounds,sites_upper_bounds=get_bounds_from_sites(
      unit_cell=ncs_group_obj.crystal_symmetry.unit_cell(),
      sites_cart=sites_cart,map_data=map_data)
  print >>out,"Original bounds: %5s  %5s  %5s  to %5s  %5s  %5s" %(
    tuple(lower_bounds+upper_bounds))
  lower_bounds=get_lower(lower_bounds,sites_lower_bounds)
  upper_bounds=get_upper(upper_bounds,sites_upper_bounds)
  print >>out,"Updated bounds:  %5s  %5s  %5s  to %5s  %5s  %5s" %(
    tuple(lower_bounds+upper_bounds))

  lower_bounds,upper_bounds=adjust_bounds(params,lower_bounds,upper_bounds,
    map_data=map_data,out=out)

  print >>out,\
     "\nMaking two types of maps for AU of NCS mask and map with "+\
      "buffer of %d grid units \nin each direction around AU" %(
      params.output_files.box_buffer)
  print >>out,"Both types of maps have the same origin and overlay on %s" %(
   os.path.join(tracking_data.params.output_files.output_directory,
     params.output_files.shifted_map_file))


  print >>out,\
     "\nThe standard maps (%s, %s) have the \noriginal cell dimensions." %(
   os.path.join(tracking_data.params.output_files.output_directory,au_mask_output_file),
   os.path.join(tracking_data.params.output_files.output_directory,au_map_output_file))+\
   "\nThese maps show only the unique (NCS AU) part of the map."

  print >>out,\
     "\nThe cut out box_maps (%s, %s) have \nsmaller cell dimensions." %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_mask_file),
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_map_file),) +\
   "\nThese maps also show only the unique part of the map and have this"+\
   "\nunique part cut out.\n"


  # Write out NCS AU with shifted origin but initial crystal_symmetry
  # Mask
  mask_data_ncs_au=get_bool_mask_as_int(
     ncs_group_obj=ncs_group_obj,mask_as_bool=bool_selected_regions)

  if au_mask_output_file: # Write out the mask (as int)
    write_ccp4_map(tracking_data.crystal_symmetry,
      au_mask_output_file,mask_data_ncs_au)
    print >>out,"Output NCS AU mask:  %s" %(au_mask_output_file)
    tracking_data.set_output_ncs_au_mask_info(
      file_name=au_mask_output_file,
      crystal_symmetry=tracking_data.crystal_symmetry,
      origin=mask_data_ncs_au.origin(),
      all=mask_data_ncs_au.all())

  # Map
  map_data_ncs_au=map_data.deep_copy()
  s=(bool_selected_regions==True)
  mask=map_data.deep_copy()
  mask=mask.set_selected(s,1)
  mask=mask.set_selected(~s,0)
  map_data_ncs_au=map_data_ncs_au*mask

  one_d=map_data_ncs_au.as_1d()
  n_zero=mask.count(0)
  n_tot=mask.size()
  mean_in_box=one_d.min_max_mean().mean*n_tot/(n_tot-n_zero)
  map_data_ncs_au=map_data_ncs_au+(1-mask)*mean_in_box
  del one_d,mask

  if au_map_output_file: # Write out the NCS au of density
    write_ccp4_map(tracking_data.crystal_symmetry,au_map_output_file,
      map_data_ncs_au)
    print >>out,"Output NCS AU map:  %s" %(au_map_output_file)
    tracking_data.set_output_ncs_au_map_info(
      file_name=au_map_output_file,
      crystal_symmetry=tracking_data.crystal_symmetry,
      origin=map_data_ncs_au.origin(),
      all=map_data_ncs_au.all())

  # Now box_map of cut out AU

  box_mask_ncs_au,box_crystal_symmetry=cut_out_map(
       map_data=mask_data_ncs_au.as_double(),
       crystal_symmetry=tracking_data.crystal_symmetry,
       min_point=lower_bounds, max_point=upper_bounds,out=out)

  # Mask
  if params.output_files.box_mask_file:
    # write out box_map NCS mask representing one AU of the NCS
    write_ccp4_map(
     box_crystal_symmetry,
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_mask_file),
      box_mask_ncs_au)
    print >>out,\
      "Output NCS au as box (cut out) mask:  %s " %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_mask_file))
    tracking_data.set_output_box_mask_info(
      file_name=os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_mask_file),
      crystal_symmetry=box_crystal_symmetry,
      origin=box_mask_ncs_au.origin(),
      all=box_mask_ncs_au.all())

  # Map
  if params.output_files.box_map_file:
    # write out NCS map as box_map (cut out region of map enclosed in box_mask)
    box_map_ncs_au,box_crystal_symmetry=cut_out_map(
       map_data=map_data_ncs_au.as_double(),
       crystal_symmetry=tracking_data.crystal_symmetry,
       min_point=lower_bounds, max_point=upper_bounds,out=out)
    write_ccp4_map(box_crystal_symmetry,
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_map_file),
      box_map_ncs_au)
    print >>out,"Output NCS au as box (cut out) map:  %s " %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_map_file))
    tracking_data.set_output_box_map_info(
      file_name=os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_map_file),
      crystal_symmetry=box_crystal_symmetry,
      origin=box_map_ncs_au.origin(),
      all=box_map_ncs_au.all())



  # Write out all the selected regions
  print >>out,"\nWriting out region maps. "+\
    "These superimpose on the NCS AU map \nand "+\
    "mask %s,%s\n" %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_map_file),
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.box_mask_file),)

  map_files_written,remainder_regions_written=write_region_maps(params,
    map_data=map_data,
    tracking_data=tracking_data,
    ncs_group_obj=ncs_group_obj,
    remainder_ncs_group_obj=remainder_ncs_group_obj,
    out=out)

  # and pick up the remainder regions not already written
  remainder_map_files_written,dummy_remainder=write_region_maps(params,
    map_data=map_data,
    tracking_data=tracking_data,
    ncs_group_obj=remainder_ncs_group_obj,
    regions_to_skip=remainder_regions_written,
    out=out)
  map_files_written+=remainder_map_files_written
  return map_files_written

def write_intermediate_maps(params,
    map_data=None,
    map_data_remaining=None,
    ncs_group_obj=None,
    tracking_data=None,
    out=sys.stdout):

  if map_data_remaining and params.output_files.remainder_map_file:
    write_ccp4_map(
       tracking_data.crystal_symmetry,params.output_files.remainder_map_file,
      map_data_remaining)
    print >>out,"Wrote output remainder map to %s" %(
       params.output_files.remainder_map_file)

  if params.segmentation.write_all_regions:
    for id in ncs_group_obj.selected_regions:
      region_mask=ncs_group_obj.edited_mask.deep_copy()
      s = (ncs_group_obj.edited_mask == -1)
      s |= (ncs_group_obj.edited_mask==id)
      region_mask = region_mask.set_selected(s,1)
      region_mask = region_mask.set_selected(~s,0)

      write_ccp4_map(tracking_data.crystal_symmetry,
          'mask_%d.ccp4' %id, region_mask)
      print >>out,"Wrote output mask for region %d to %s" %(id,
        "mask_%d.ccp4" %(id))


def iterate_search(params,
      map_data_remaining=None,
      map_data=None,
      ncs_obj=None,
      ncs_group_obj=None,
      scattered_points=None,
      tracking_data=None,
      out=sys.stdout):


  # Write out intermediate maps if desired
  if params.output_files.write_intermediate_maps:
    write_intermediate_maps(params,
      map_data=map_data,
      map_data_remaining=map_data_remaining,
      ncs_group_obj=ncs_group_obj,
      tracking_data=tracking_data,
      out=out)
  new_params=deepcopy(params)
  new_params.segmentation.iterate_with_remainder=False
  new_params.segmentation.density_threshold=None
  new_params.output_files.write_output_maps=False
  new_params.output_files.output_info_file=None
  if params.output_files.write_intermediate_maps:
    new_params.output_files.au_output_file_stem=\
      params.output_files.au_output_file_stem+"_cycle_2"
  else:
    new_params.output_files.au_output_file_stem=None

  fraction=0.2
  new_n_residues=int(tracking_data.n_residues*fraction)
  new_solvent_fraction=max(0.001,min(0.999,
      1- (1-tracking_data.solvent_fraction)*fraction))

  new_tracking_data=deepcopy(tracking_data)
  new_tracking_data.set_n_residues(new_n_residues)
  new_tracking_data.set_solvent_fraction(new_solvent_fraction)
  new_tracking_data.set_origin_shift() # sets it to zero
  new_tracking_data.params.segmentation.starting_density_threshold=new_params.segmentation.starting_density_threshold # this is new
  print >>out,"\nIterating with remainder density"
  # NOTE: do not include pdb_hierarchy here unless you deep_copy it
  remainder_ncs_group_obj,dummy_remainder,remainder_tracking_data=run(
    None,params=new_params,
    map_data=map_data_remaining,
    ncs_obj=ncs_obj,
    target_scattered_points=scattered_points,
    tracking_data=new_tracking_data,
    is_iteration=True,
    out=out)
  if not remainder_ncs_group_obj: # Nothing to do
    return None

  # Combine the results to get remainder_id_dict
  #   remainder_id_dict[id_remainder]=id_nearby

  remainder_ncs_group_obj=combine_with_iteration(params,
     map_data=map_data,
     crystal_symmetry=tracking_data.crystal_symmetry,
     ncs_group_obj=ncs_group_obj,
     remainder_ncs_group_obj=remainder_ncs_group_obj,
     out=out)

  return remainder_ncs_group_obj

def bounds_overlap(lower=None,upper=None,
          other_lower=None,other_upper=None,tol=1):
   for i in xrange(3):
     if       upper[i]+tol<other_lower[i]: return False
     if other_upper[i]+tol<lower[i]:       return False
   return True

def combine_with_iteration(params,
    map_data=None,
    crystal_symmetry=None,
    ncs_group_obj=None,
    remainder_ncs_group_obj=None,
    out=sys.stdout):

  if not ncs_group_obj.selected_regions or not remainder_ncs_group_obj \
      or not remainder_ncs_group_obj.selected_regions:
    return None

  # see if any regions in ncs_obj overlap with remainder_ncs_group_obj...
  #   If so, combine


  remainder_id_dict={}
  for id_remainder in remainder_ncs_group_obj.selected_regions:
    best_id=None
    best_overlaps=None
    remainder_centers=\
        remainder_ncs_group_obj.region_scattered_points_dict[id_remainder]
    # figure out typical distance between scattered_points...
    touching_dist=get_touching_dist(remainder_centers)

    # Notice bounds of remainder region:
    r_lower,r_upper=get_bounds(
       ncs_group_obj=remainder_ncs_group_obj,id=id_remainder)

    for id in ncs_group_obj.selected_regions:
      # Skip if not likely to be very close...
      lower,upper=get_bounds(ncs_group_obj=ncs_group_obj,id=id)
      if not bounds_overlap(lower=lower,upper=upper,
          other_lower=r_lower,other_upper=r_upper):
        continue

      test_centers=ncs_group_obj.region_scattered_points_dict[id]
      dist=get_closest_dist(test_centers,remainder_centers)
      if touching_dist is not None and dist>touching_dist:
        continue

      bool_region_mask = ncs_group_obj.co.expand_mask(
        id_to_expand=ncs_group_obj.original_id_from_id[id],
        expand_size=params.segmentation.expand_size+1) # just touching
      s = (bool_region_mask== True)
      s &=  (remainder_ncs_group_obj.edited_mask==id_remainder)
      overlaps=s.count(True)
      if best_overlaps is None or overlaps>best_overlaps:
        best_overlaps=overlaps
        best_id=id
    if best_overlaps:
      print >>out,\
        "\nCombining remainder id %d with original id %d (overlaps=%d)" %(
        id_remainder,best_id,best_overlaps)
      remainder_id_dict[id_remainder]=best_id
  remainder_ncs_group_obj.remainder_id_dict=remainder_id_dict
  return remainder_ncs_group_obj

def get_touching_dist(centers,default=100.,min_dist=8.):
  mean_dist=0.
  mean_dist_n=0.
  nskip=max(1,len(centers)//10) # try to get 10
  for i in xrange(0,len(centers),nskip):
     if i==0:
       target=centers[1:]
     elif i==len(centers)-1:
       target=centers[:-1]
     else:
       target=centers[:i]
       target.extend(centers[i+1:])
     other=centers[i:i+1]
     if not target or not other: continue
     dist=get_closest_dist(target,other)
     if dist is not None:
       mean_dist+=dist
       mean_dist_n+=1.
  if mean_dist_n>0:
    return max(min_dist,2.0*mean_dist/mean_dist_n)
  else:
    return default

def get_grid_units(map_data=None,crystal_symmetry=None,radius=None,
     out=sys.stdout):
    N_ = map_data.all()
    sx,sy,sz= 1/N_[0], 1/N_[1], 1/N_[2]
    sx_cart,sy_cart,sz_cart=crystal_symmetry.unit_cell().orthogonalize(
       [sx,sy,sz])
    grid_spacing=(sx_cart+sy_cart+sz_cart)/3.
    grid_units=int(radius/grid_spacing)
    min_cell_grid_units=min(N_[0], N_[1], N_[2])
    grid_units=min(grid_units,int(min_cell_grid_units/3))
    print "Grid units representing %7.1f A will be %d" %(
       radius,grid_units)
    return grid_units

def cut_out_map(map_data=None, crystal_symmetry=None,
    soft_mask=None,soft_mask_radius=None,resolution=None,
    shift_origin=None,
    min_point=None,max_point=None,out=sys.stdout):
  from cctbx import uctbx
  from cctbx import maptbx
  na = map_data.all() # tuple with dimensions
  for i in range(3):
    assert min_point[i] >= 0
    assert max_point[i] <= na[i]
  new_map_data = maptbx.copy(map_data, tuple(min_point), tuple(max_point))
  # shrink unit cell, angles are the same
  shrunk_uc = []
  for i in range(3):
    shrunk_uc.append(
     crystal_symmetry.unit_cell().parameters()[i]*new_map_data.all()[i]/na[i] )
  uc_params=crystal_symmetry.unit_cell().parameters()
  new_unit_cell_box = uctbx.unit_cell(
    parameters=(shrunk_uc[0],shrunk_uc[1],shrunk_uc[2],
        uc_params[3],uc_params[4],uc_params[5]))
  new_crystal_symmetry=crystal.symmetry(
    unit_cell=new_unit_cell_box,space_group='p1')


  if soft_mask and soft_mask_radius is not None:
    assert shift_origin  # need to do this
    if shift_origin:
      new_map_data = new_map_data.shift_origin()

    # Add soft boundary to mean around outside of mask
    # grid_units is how many grid units are about equal to soft_mask_radius 
    grid_units=get_grid_units(map_data=new_map_data,
      crystal_symmetry=new_crystal_symmetry,radius=soft_mask_radius,out=out)
    grid_units=int(0.5+0.5*grid_units)
    acc=map_data.accessor()
    from cctbx import maptbx
    zero_boundary_map=maptbx.zero_boundary_box_map(
       new_map_data,grid_units).result()
    # this map is zero's around the edge and 1 in the middle
    # multiply zero_boundary_map--smoothed & new_map_data and return
    print >>out,"Applying soft mask to boundary of cut out map"
    #write_ccp4_map(new_crystal_symmetry,'before.ccp4',new_map_data)
    new_map_data=apply_soft_mask(map_data=new_map_data,
          mask_data=zero_boundary_map,
          rad_smooth=resolution,
          crystal_symmetry=new_crystal_symmetry,
          out=out)
    #write_ccp4_map(new_crystal_symmetry,'after.ccp4',new_map_data)

  return new_map_data, new_crystal_symmetry

def apply_shift_to_pdb_hierarchy(
    origin_shift=None,
    crystal_symmetry=None,
    pdb_hierarchy=None,out=sys.stdout):

  if origin_shift is not None:
    sites_cart=pdb_hierarchy.atoms().extract_xyz()
    sites_cart_shifted=sites_cart+\
      flex.vec3_double(sites_cart.size(), origin_shift)
    pdb_hierarchy.atoms().set_xyz(sites_cart_shifted)

  return pdb_hierarchy

def apply_origin_shift(origin_shift=None,
    ncs_object=None,
    pdb_hierarchy=None,
    target_hierarchy=None,
    map_data=None,
    shifted_map_file=None,
    shifted_pdb_file=None,
    shifted_ncs_file=None,
    tracking_data=None,
    sharpening_target_pdb_inp=None,
    out=sys.stdout):

  if shifted_map_file:
      write_ccp4_map(tracking_data.crystal_symmetry,
      shifted_map_file,
      map_data)
      print >>out,"Wrote shifted map to %s" %(
        shifted_map_file)
      tracking_data.set_shifted_map_info(file_name=
        shifted_map_file,
        crystal_symmetry=tracking_data.crystal_symmetry,
        origin=map_data.origin(),
        all=map_data.all())
  if origin_shift: # Note origin shift does not change crystal_symmetry

    if pdb_hierarchy:
      pdb_hierarchy=apply_shift_to_pdb_hierarchy(
       origin_shift=origin_shift,
       crystal_symmetry=tracking_data.crystal_symmetry,
       pdb_hierarchy=pdb_hierarchy,
       out=out)

    if sharpening_target_pdb_inp:
      sharpening_target_pdb_inp=apply_shift_to_pdb_hierarchy(
       origin_shift=origin_shift,
       crystal_symmetry=tracking_data.crystal_symmetry,
       pdb_hierarchy=sharpening_target_pdb_inp.construct_hierarchy(),
       out=out).as_pdb_input()

    if target_hierarchy:
      target_hierarchy=apply_shift_to_pdb_hierarchy(
       origin_shift=origin_shift,
       crystal_symmetry=tracking_data.crystal_symmetry,
       pdb_hierarchy=target_hierarchy,
       out=out)

    from scitbx.math import  matrix
    ncs_object=ncs_object.coordinate_offset(
       coordinate_offset=matrix.col(origin_shift))


  if shifted_pdb_file and pdb_hierarchy:
      import iotbx.pdb
      f=open(shifted_pdb_file,'w')
      print >>f, iotbx.pdb.format_cryst1_record(
         crystal_symmetry=tracking_data.crystal_symmetry)
      print >>f,pdb_hierarchy.as_pdb_string()
      f.close()
      print >>out,"Wrote shifted pdb file to %s" %(
        shifted_pdb_file)
      tracking_data.set_shifted_pdb_info(file_name=shifted_pdb_file,
      n_residues=pdb_hierarchy.overall_counts().n_residues)


  if shifted_ncs_file:
      ncs_object.format_all_for_group_specification(
         file_name=shifted_ncs_file)
      print >>out,"Wrote %s NCS operators for shifted map to %s" %(
         ncs_object.max_operators(),
         shifted_ncs_file)
      if tracking_data.input_ncs_info.has_updated_operators():
        print >>out,\
        "NOTE: these may include additional operators added to fill the cell"
      tracking_data.set_shifted_ncs_info(file_name=shifted_ncs_file,
        number_of_operators=ncs_object.max_operators(),
        is_helical_symmetry=tracking_data.input_ncs_info.is_helical_symmetry)
      tracking_data.shifted_ncs_info.show_summary(out=out)

  return ncs_object,pdb_hierarchy,target_hierarchy,tracking_data,\
     sharpening_target_pdb_inp

def restore_pdb(params,tracking_data=None,out=sys.stdout):
  if not params.output_files.restored_pdb:
    params.output_files.restored_pdb=\
       params.input_files.pdb_to_restore[:-4]+"_restored.pdb"
  print>>out,"Shifting origin of %s and writing to %s" %(
    params.input_files.pdb_to_restore,
    params.output_files.restored_pdb)
  os=tracking_data.origin_shift
  origin_shift=(-os[0],-os[1],-os[2])
  print >>out,"Origin shift will be: %.1f  %.1f  %.1f "%(origin_shift)

  import iotbx.pdb
  pdb_inp = iotbx.pdb.input(file_name=params.input_files.pdb_to_restore)
  pdb_hierarchy = pdb_inp.construct_hierarchy()
  pdb_hierarchy=apply_shift_to_pdb_hierarchy(
    origin_shift=origin_shift,
    crystal_symmetry=tracking_data.crystal_symmetry,
    pdb_hierarchy=pdb_hierarchy,
    out=out)

  f=open(params.output_files.restored_pdb,'w')
  print >>f, iotbx.pdb.format_cryst1_record(
      crystal_symmetry=tracking_data.crystal_symmetry)
  print >>f,pdb_hierarchy.as_pdb_string()
  f.close()
  print >>out,"Wrote restored pdb file to %s" %(
     params.output_files.restored_pdb)

def find_threshold_in_map(target_points=None,
      map_data=None,
      iter_max=10):

  map_1d=map_data.as_1d()
  map_mean=map_1d.min_max_mean().mean
  map_max=map_1d.min_max_mean().max
  map_min=map_1d.min_max_mean().min

  cutoff=map_mean
  low=map_min
  high=map_max

  for iter in xrange(iter_max):
    s = (map_1d >cutoff)
    n_cutoff=s.count(True)
    if n_cutoff == target_points:
      return cutoff
    elif n_cutoff < target_points: # lower it
      high=cutoff
      cutoff=0.5*(cutoff+low)
    else:  # raise it
      low=cutoff
      cutoff=0.5*(cutoff+high)
  return cutoff


def remove_points(mask,remove_points=None):
  keep_points=(remove_points==False)
  new_mask=(mask & keep_points)
  return new_mask

def get_ncs_sites_cart(sites_cart=None,
     ncs_obj=None, unit_cell=None, ncs_in_cell_only=True):

  ncs_sites_cart=flex.vec3_double()
  if not ncs_obj or not ncs_obj.ncs_groups() or not ncs_obj.ncs_groups()[0] or \
     not ncs_obj.ncs_groups()[0].translations_orth():
    return ncs_sites_cart

  # identify ncs-related points
  ncs_group=ncs_obj.ncs_groups()[0]
  identity_op=ncs_group.identity_op_id()
  ncs_sites_cart=flex.vec3_double()
  for xyz_cart in sites_cart:
    for i0 in xrange(len(ncs_group.translations_orth())):
      if i0==identity_op: continue
      r=ncs_group.rota_matrices_inv()[i0] # inverse maps pos 0 on to pos i
      t=ncs_group.translations_orth_inv()[i0]
      new_xyz_cart=r * matrix.col(xyz_cart) + t
      ncs_sites_cart.append(new_xyz_cart)
  if ncs_in_cell_only:
    new_sites_cart=flex.vec3_double()
    ncs_sites_frac=unit_cell.fractionalize(ncs_sites_cart)
    for site_frac,site_cart in zip(ncs_sites_frac,ncs_sites_cart):
      if site_frac[0]>=0 and site_frac[0]<=1 and  \
         site_frac[1]>=0 and site_frac[1]<=1 and  \
         site_frac[2]>=0 and site_frac[2]<=1:
        new_sites_cart.append(site_cart)
    ncs_sites_cart=new_sites_cart

  return ncs_sites_cart

def get_ncs_mask(map_data=None,unit_cell=None,ncs_object=None,
   starting_mask=None,radius=None,expand_radius=None,overall_mask=None,
   every_nth_point=None):

  assert every_nth_point is not None
  if not expand_radius: expand_radius=2.*radius

  working_au_mask=starting_mask.deep_copy()

  working_ncs_mask=mask_from_sites_and_map(  # empty ncs mask
    map_data=map_data,unit_cell=unit_cell,
    sites_cart=flex.vec3_double(),radius=radius,overall_mask=overall_mask)

  au_points_last=working_au_mask.count(True)
  ncs_points_last=working_ncs_mask.count(True)

  max_tries=10000
  for ii in xrange(max_tries): # just a big number; should take just a few

    # Find all points in au (sample every_nth_point in grid)

    au_sites_cart=get_marked_points_cart(mask_data=working_au_mask,
     unit_cell=unit_cell,every_nth_point=every_nth_point,
     boundary_radius=radius)

    # Find all points ncs-related to marked point in mask
    ncs_sites_cart=get_ncs_sites_cart(sites_cart=au_sites_cart,
       ncs_obj=ncs_object,unit_cell=unit_cell,ncs_in_cell_only=True)

    # Expand au slightly with all points near to au_sites_cart
    new_au_mask=mask_from_sites_and_map(
      map_data=map_data,unit_cell=unit_cell,
      sites_cart=au_sites_cart,radius=radius,overall_mask=overall_mask)
    working_au_mask=(working_au_mask | new_au_mask) # add on to existing
    keep_points=(working_ncs_mask==False)  # cross off those in  ncs
    working_au_mask=(working_au_mask & keep_points)

    # mark ncs au with all points not in au that are close to ncs_sites_cart
    new_ncs_mask=mask_from_sites_and_map(
      map_data=map_data,unit_cell=unit_cell,
      sites_cart=ncs_sites_cart,radius=radius,overall_mask=overall_mask)
    keep_points=(working_au_mask==False)  # cross off those in au
    new_ncs_mask=(new_ncs_mask & keep_points)
    working_ncs_mask=(new_ncs_mask | working_ncs_mask) # add on to existing

    au_points=working_au_mask.count(True)
    ncs_points=working_ncs_mask.count(True)
    if au_points==au_points_last and ncs_points==ncs_points_last:
      break
    au_points_last=au_points
    ncs_points_last=ncs_points
    # Now expand the au and repeat

    working_au_mask=mask_from_sites_and_map(
      map_data=map_data,unit_cell=unit_cell,
      sites_cart=au_sites_cart,radius=expand_radius,overall_mask=overall_mask)
    keep_points=(working_ncs_mask==False)  # cross off those in  ncs
    working_au_mask=(working_au_mask & keep_points)

  return working_au_mask,working_ncs_mask

def renormalize_map_data(
  map_data=None,solvent_fraction=None):
  sd=max(0.0001,map_data.sample_standard_deviation())
  if solvent_fraction >= 10.: solvent_fraction=solvent_fraction/100.
  assert solvent_fraction > 0 and solvent_fraction < 1
  scaled_sd=sd/(1-solvent_fraction)**0.5
  map_data=(map_data-map_data.as_1d().min_max_mean().mean)/scaled_sd
  return map_data


def mask_from_sites_and_map(
    map_data=None,unit_cell=None,
    sites_cart=None,radius=None,overall_mask=None):
  assert radius is not None
  from cctbx import maptbx

  sel = maptbx.grid_indices_around_sites(
      unit_cell  = unit_cell,
      fft_n_real = map_data.focus(),
      fft_m_real = map_data.all(),
      sites_cart = sites_cart,
      site_radii = flex.double(sites_cart.size(), radius))
  map_data_1d=map_data.as_1d()
  mask=(map_data_1d==0 and map_data_1d==1)  # 1D bool array all False
  mask.set_selected(sel, True)  # mark points around sites
  mask.reshape(map_data.accessor())
  if overall_mask:
    assert overall_mask.all()==mask.all()
    mask=(mask & overall_mask)
  return mask

def set_radius(unit_cell=None,map_data=None,every_nth_point=None):
  # Set radius so that radius will capture all points on grid if sampled
  #  on every_nth_point
  a,b,c = unit_cell.parameters()[:3]
  nx,ny,nz=map_data.all()
  # furthest possible minimum distance between grid points
  max_diagonal_between_sampled=every_nth_point*(
      (a/nx)**2+(b/ny)**2+(c/nz)**2)**0.5
  radius=max_diagonal_between_sampled*0.55  # big enough to cover everything
  return radius

def get_marked_points_cart(mask_data=None,unit_cell=None,
   every_nth_point=3,boundary_radius=None):
  # return list of cartesian coordinates of grid points that are marked
  # only sample every every_nth_point in each direction...
  assert mask_data.origin() == (0,0,0)
  nx,ny,nz=mask_data.all()
  if boundary_radius:
    # How far from edges shall we stay:
    grid_frac=(1./nx,1./ny,1./nz)
    grid_orth=unit_cell.orthogonalize(grid_frac)
    boundary_grid_points=0
    for go in grid_orth:
      bgp=int(0.99+boundary_radius/go)
      boundary_grid_points=max(boundary_grid_points,bgp)
  else:
    boundary_grid_points=0


  marked_points=maptbx.marked_grid_points(
    map_data=mask_data,
    every_nth_point=every_nth_point).result()
  sites_frac=flex.vec3_double()
  boundary_points_skipped=0
  for grid_point in marked_points:
    if boundary_grid_points:
      if \
         grid_point[0]<boundary_grid_points or \
         grid_point[0]>nx-boundary_grid_points or \
         grid_point[1]<boundary_grid_points or \
         grid_point[0]>ny-boundary_grid_points or \
         grid_point[2]<boundary_grid_points or \
         grid_point[0]>nz-boundary_grid_points:
        boundary_points_skipped+=1
        continue
    sites_frac.append(
        (grid_point[0]/nx,
         grid_point[1]/ny,
         grid_point[2]/nz))

  sites_cart=unit_cell.orthogonalize(sites_frac)
  return sites_cart

def get_overall_mask(
    map_data=None,
    mask_threshold=None,
    solvent_fraction=None,
    crystal_symmetry=None,
    radius=None,
    resolution=None,
    out=sys.stdout):

  # Make a local SD map from our map-data
  from cctbx.maptbx import crystal_gridding
  cg=crystal_gridding(
        unit_cell=crystal_symmetry.unit_cell(),
        space_group_info=crystal_symmetry.space_group_info(),
        pre_determined_n_real=map_data.all())

  if not resolution:
    from cctbx.maptbx import d_min_from_map
    resolution=d_min_from_map(
      map_data,crystal_symmetry.unit_cell(), resolution_factor=1./4.)
    print >>out,"\nEstimated resolution of map: %6.1f A\n" %(
     resolution)

  if radius:
    smoothing_radius=2.*radius
  else:
    smoothing_radius=2.*resolution

  from mmtbx.command_line.map_to_structure_factors import run as map_to_sf
  args=['d_min=None','box=True']
  for d_min in [resolution,resolution+0.5,resolution+1.0,resolution+2.]:
    args=['d_min=%s' %(d_min)]
    from libtbx.utils import null_out
    try:
      map_coeffs=map_to_sf(args=args,
         space_group_number=crystal_symmetry.space_group().type().number(),
         ccp4_map=make_ccp4_map(map_data,crystal_symmetry.unit_cell()),
         return_as_miller_arrays=True,nohl=True,out=null_out())
    except Exception,e:
      map_coeffs=None
      msg=str(e)
      continue
    break # was fine
  if not map_coeffs:
    raise Sorry(msg)

  complete_set = map_coeffs.complete_set()
  stol = flex.sqrt(complete_set.sin_theta_over_lambda_sq().data())
  import math
  w = 4 * stol * math.pi * smoothing_radius
  sphere_reciprocal = 3 * (flex.sin(w) - w * flex.cos(w))/flex.pow(w, 3)

  temp = complete_set.structure_factors_from_map(
      flex.pow2(map_data-map_data.as_1d().min_max_mean().mean))
  fourier_coeff=complete_set.array(data=temp.data()*sphere_reciprocal)
  sd_map=fourier_coeff.fft_map(
      crystal_gridding=cg,
      ).apply_volume_scaling().real_map_unpadded()
  assert sd_map.all()==map_data.all()
  # now use sd_map

  # First mask out the map based on threshold
  mm=sd_map.as_1d().min_max_mean()
  max_in_map=mm.max
  mean_in_map=mm.mean
  min_in_map=mm.min
  print >>out,"Highest value in map is %7.2f. Mean is %7.2f .  Lowest is %7.2f " %(
    max_in_map,
    mean_in_map,
    min_in_map)

  if mask_threshold:
    print >>out,"Cutoff for mask will be input threshold"
    threshold=mask_threshold
  else:  # guess based on solvent_fraction
    threshold=find_threshold_in_map(target_points=int(
      (1.-solvent_fraction)*sd_map.size()),
      map_data=sd_map)
    print >>out,"Cutoff will be threshold marking about %7.1f%% of cell" %(
      100.*(1.-solvent_fraction))

  overall_mask=(sd_map>= threshold)
  print >>out,"Model region of map "+\
    "(density above %7.3f )" %( threshold) +" includes %7.1f%% of map" %(
      100.*overall_mask.count(True)/overall_mask.size())
  return overall_mask,max_in_map,sd_map

def get_skew(data=None):
  mean=data.min_max_mean().mean
  sd=data.standard_deviation_of_the_sample()
  x=data-mean
  return (x**3).min_max_mean().mean/sd**3

def get_kurtosis(data=None):
  mean=data.min_max_mean().mean
  sd=data.standard_deviation_of_the_sample()
  x=data-mean
  return (x**4).min_max_mean().mean/sd**4

def score_map(map_data=None,
        sharpening_info_obj=None,
        solvent_fraction=None,
        fraction_occupied=None,
        wrapping=None,
        sa_percent=None,
        region_weight=None,
        max_regions_to_test=None,
        out=sys.stdout):
  if sharpening_info_obj:
    solvent_fraction=sharpening_info_obj.solvent_fraction
    wrapping=sharpening_info_obj.wrapping
    fraction_occupied=sharpening_info_obj.fraction_occupied
    sa_percent=sharpening_info_obj.sa_percent
    region_weight=sharpening_info_obj.region_weight
    max_regions_to_test=sharpening_info_obj.max_regions_to_test
  else:
    sharpening_info_obj=sharpening_info()
  if solvent_fraction is None:  # skip SA score
    sharpening_info_obj.adjusted_sa=0.
    assert sharpening_info_obj.sharpening_target=='kurtosis'
  else:  # usual
    map_data=renormalize_map_data(
       map_data=map_data,solvent_fraction=solvent_fraction)

    target_in_all_regions=map_data.size()*fraction_occupied*(1-solvent_fraction)
    print >>out,"\nTarget number of points in all regions: %.0f" %(
      target_in_all_regions)

    threshold=find_threshold_in_map(target_points=int(
         target_in_all_regions),map_data=map_data)
    print >>out,"Cutoff will be threshold of %7.2f marking %7.1f%% of cell" %(
              threshold,100.*(1.-solvent_fraction))
    co = maptbx.connectivity(map_data=map_data.deep_copy(),
           threshold=threshold,
           wrapping=wrapping,)
    z = zip(co.regions(),range(0,co.regions().size()))
    sorted_by_volume = sorted(z, key=lambda x: x[0], reverse=True)
    if len(sorted_by_volume)<2:
      return sharpening_info_obj# skip it, nothing to do

    target_sum= sa_percent* target_in_all_regions*0.01
    print >>out,"Points for %.1f percent of target in all regions: %.1f" %(
        sa_percent,target_sum)

    cntr=0
    sum_v=0.
    sum_new_v=0.
    for p in sorted_by_volume[1:max_regions_to_test+2]:
      cntr+=1
      v,i=p
      sum_v+=v
      bool_expanded=co.expand_mask(id_to_expand=i,expand_size=1)
      new_v=bool_expanded.count(True)-v
      sum_new_v+=new_v
      sa_ratio=new_v/v
      if sum_v>=target_sum: break
    sa_ratio=sum_new_v/max(1.,sum_v) # ratio of SA to volume
    regions=len(sorted_by_volume[1:])
    normalized_regions=regions/max(1,target_in_all_regions)
    skew=get_skew(map_data.as_1d())
    sharpening_info_obj.adjusted_sa=sa_ratio - region_weight*normalized_regions
    sharpening_info_obj.sa_ratio=sa_ratio
    sharpening_info_obj.normalized_regions=normalized_regions

  sharpening_info_obj.kurtosis=get_kurtosis(map_data.as_1d())
  if sharpening_info_obj.sharpening_target=='kurtosis':
    sharpening_info_obj.score=sharpening_info_obj.kurtosis
  else:
    sharpening_info_obj.score=sharpening_info_obj.adjusted_sa
  return sharpening_info_obj

def sharpen_map_with_si(sharpening_info_obj=None,
     f_array_normalized=None,
     f_array=None,phases=None,
     map_data=None,
     overall_b=None,
     resolution=None,
     out=sys.stdout):

  si=sharpening_info_obj

  if si.sharpening_method=='no_sharpening':
     return map_data # do nothing

  if map_data and (not f_array or not phases):
    map_coeffs,dummy=get_f_phases_from_map(map_data=map_data,
       crystal_symmetry=si.crystal_symmetry,
       d_min=si.resolution,
       d_min_ratio=si.d_min_ratio,
       return_as_map_coeffs=True,
       out=out)
    f_array,phases=map_coeffs_as_fp_phi(map_coeffs)

  if si.remove_aniso: 
    if si.use_local_aniso and \
      (si.local_aniso_in_local_sharpening or 
       (si.local_aniso_in_local_sharpening is None and si.ncs_copies==1)) and \
         si.original_aniso_obj: # use original
      aniso_obj=si.original_aniso_obj
      print >>out,\
       "\nRemoving aniso from map using saved aniso object before sharpening\n"
    else:
      print >>out,"\nRemoving aniso from map before sharpening\n"
      aniso_obj=None
    from cctbx.maptbx.refine_sharpening import analyze_aniso
    f_array,f_array_ra=analyze_aniso(
        aniso_obj=aniso_obj,
        remove_aniso=si.remove_aniso,
        f_array=f_array,resolution=si.resolution,out=out)
     
  if si.is_model_sharpening() or si.is_half_map_sharpening():
    from cctbx.maptbx.refine_sharpening import scale_amplitudes
    return scale_amplitudes(
      map_coeffs=f_array.phase_transfer(phase_source=phases,deg=True),
      si=si,overall_b=overall_b,out=out)

  elif si.is_resolution_dependent_sharpening():
    if f_array_normalized is None:

      from cctbx.maptbx.refine_sharpening import get_sharpened_map,\
       quasi_normalize_structure_factors
      (d_max,d_min)=f_array.d_max_min()
      if not f_array.binner():
        f_array.setup_binner(n_bins=si.n_bins,d_max=d_max,d_min=d_min)
      f_array_normalized=quasi_normalize_structure_factors(
          f_array,set_to_minimum=0.01)
    return get_sharpened_map(ma=f_array_normalized,phases=phases,
       b=si.resolution_dependent_b,resolution=si.resolution,n_real=si.n_real,
       d_min_ratio=si.d_min_ratio)

  else:
    return apply_sharpening(n_real=si.n_real,
          f_array=f_array,phases=phases,
          sharpening_info_obj=si,
          crystal_symmetry=si.crystal_symmetry,
          out=null_out())

def put_bounds_in_range(
     lower_bounds=None,upper_bounds=None,
     box_size=None,
     buffer=None,
     n_real=None,out=sys.stdout):
  # put lower and upper inside (0,n_real) and try to make size at least minimum

  new_lb=[]
  new_ub=[]
  print >>out,"Putting bounds in range...(%s,%s,%s) to (%s,%s,%s)" %(
       tuple(list(lower_bounds)+list(upper_bounds)))
  if buffer:
     print >>out,"Buffer of %s added" %(buffer)
  for lb,ub,ms,nr in zip(lower_bounds,upper_bounds,box_size,n_real):
    if buffer:
       lb=lb-buffer
       ub=ub+buffer

    if lb<0:
      shift=-lb
      lb+=shift
      ub+=shift
    boundary=int(ms-(ub-lb+1))//2
    if boundary>0:
       lb=lb-boundary
       ub=ub+boundary
    if lb<0: lb=0
    if ub>nr: ub=nr
    new_lb.append(lb)
    new_ub.append(ub)
  print >>out,"New bounds ...(%s,%s,%s) to (%s,%s,%s)" %(
       tuple(list(new_lb)+list(new_ub)))
  return tuple(new_lb),tuple(new_ub)

def get_iterated_solvent_fraction(map=None,
    verbose=None,
    crystal_symmetry=None,out=sys.stdout):
  try:
    from phenix.autosol.map_to_model import iterated_solvent_fraction
    return iterated_solvent_fraction(
      crystal_symmetry=crystal_symmetry,
      map_as_double=map,
      verbose=verbose,
      return_solvent_fraction=True,
      out=out)
  except Exception,e:
    # catch case where map was not on proper grid
    if str(e).find("sym equiv of a grid point must be a grid point")>-1:
      print >>out,\
      "\nSpace group:%s \n Unit cell: %s \n Gridding: %s \nError message: %s" %(
        crystal_symmetry.space_group().info(),
        str(crystal_symmetry.unit_cell().parameters()),
        str(map.all()),str(e))
      raise Sorry(
      "The input map seems to be on a grid incompatible with crystal symmetry"+
         "\n(symmetry equivalents of a grid point must be on "+
          "an integer grid point)")

    return None  # was not available

def set_up_si(var_dict=None,crystal_symmetry=None,
      is_crystal=None,
      ncs_copies=None,n_residues=None,
      solvent_fraction=None,pdb_inp=None,map=None,
      auto_sharpen=True,half_map_data_list=None,verbose=None,
      out=sys.stdout):
    si=sharpening_info(n_real=map.all())
    args=[]
    auto_sharpen_methods=var_dict.get('auto_sharpen_methods')
    if auto_sharpen_methods and auto_sharpen_methods != ['None'] and \
        len(auto_sharpen_methods)==1:
      sharpening_method=auto_sharpen_methods[0]
    else:
      sharpening_method=None

    for param in [
       'verbose','seq_file','box_size','box_center','remove_aniso',
       'input_weight_map_pickle_file', 'output_weight_map_pickle_file',
       'read_sharpened_maps', 'write_sharpened_maps', 'select_sharpened_map',
       'output_directory',
       'smoothing_radius','use_local_aniso','local_aniso_in_local_sharpening',
       'local_sharpening','box_in_auto_sharpen','use_weak_density',
       'resolution','d_min_ratio',
       'discard_if_worse',
       'mask_atoms','mask_atoms_atom_radius','value_outside_atoms','soft_mask',
       'max_box_fraction','k_sharpen',
        'residual_target','sharpening_target',
       'search_b_min','search_b_max','search_b_n','maximum_low_b_adjusted_sa',
       'b_iso','b_sharpen',
       'resolution_dependent_b',
       'region_weight',
       'sa_percent',
       'n_bins',
       'eps',
       'max_regions_to_test',
       'fraction_occupied',
       'rmsd',
       'k_sol',
       'b_sol',
       'fraction_complete',
       'verbose',
         ]:
     x=var_dict.get(param)
     if x is not None:
       if type(x)==type([1,2,3]):
         xx=[]
         for k in x:
           xx.append(str(k))
         args.append("%s=%s" %(param," ".join(xx)))
       else:
         args.append("%s=%s" %(param,x))
    local_params=get_params_from_args(args)

    if local_params.input_files.seq_file and \
        not local_params.crystal_info.solvent_content:
        solvent_fraction=get_solvent_fraction(local_params,
          crystal_symmetry=crystal_symmetry,
          ncs_copies=ncs_copies,out=out)

    si.update_with_params(params=local_params,
      crystal_symmetry=crystal_symmetry,
      is_crystal=is_crystal,
      solvent_fraction=solvent_fraction,
      ncs_copies=ncs_copies,
      n_residues=n_residues,
      auto_sharpen=auto_sharpen,
      sharpening_method=sharpening_method,
      pdb_inp=pdb_inp,
      half_map_data_list=half_map_data_list,
      )
    return si

def select_box_map_data(si=None,
           map_data=None,
           first_half_map_data=None,
           second_half_map_data=None,
           pdb_inp=None,
           get_solvent_fraction=True,# XXX test not doing this...
           out=sys.stdout):

  solvent_fraction=si.solvent_fraction
  crystal_symmetry=si.crystal_symmetry
  max_box_fraction=si.max_box_fraction
  box_size=si.box_size
  if pdb_inp:  # use model to identify region to cut out
    from mmtbx.command_line.map_box import run as run_map_box
    args=[]
    if si.mask_atoms:
      args.append('mask_atoms=True')
      if si.mask_atoms_atom_radius:
        args.append('mask_atoms_atom_radius=%s' %(si.mask_atoms_atom_radius))
      if si.value_outside_atoms:
        args.append('value_outside_atoms=%s' %(si.value_outside_atoms))
      if si.soft_mask:
        args.append('soft_mask=%s' %(si.soft_mask))
        args.append('soft_mask_radius=%s' %(si.resolution))
    hierarchy=pdb_inp.construct_hierarchy()
    print >>out,"Getting map as box"
    box=run_map_box(args,
        map_data=map_data,pdb_hierarchy=hierarchy,
       write_output_files=False,
       crystal_symmetry=crystal_symmetry,log=out)
    box_map=box.map_box.as_double()
    box_map=scale_map(box_map,out=out)
    box_crystal_symmetry=box.box_crystal_symmetry
    box_pdb_inp=box.hierarchy.as_pdb_input()
    if first_half_map_data:
      print >>out,"Getting first map as box"
      box_first=run_map_box(args,
        map_data=first_half_map_data,pdb_hierarchy=hierarchy,
       write_output_files=False,
       crystal_symmetry=crystal_symmetry,log=out)
      box_first_half_map=box_first.map_box.as_double()
    else:
      box_first_half_map=None

    if second_half_map_data:
      print >>out,"Getting second map as box"
      box_second=run_map_box(args,
        map_data=second_half_map_data,pdb_hierarchy=hierarchy,
       write_output_files=False,
       crystal_symmetry=crystal_symmetry,log=out)
      box_second_half_map=box_second.map_box.as_double()
    else:
      box_second_half_map=None


  else:
    if si.box_center:  # center at box_center
      lower_bounds,upper_bounds=box_from_center(si=si,
        map_data=map_data,out=out)
    elif si.use_weak_density:
      lower_bounds,upper_bounds=box_of_smallest_region(si=si,
           map_data=map_data,
           out=out)
    else:
      lower_bounds,upper_bounds=box_of_biggest_region(si=si,
           map_data=map_data,
           out=out)
    if si.soft_mask:
      buffer=get_grid_units(map_data=map_data,
        crystal_symmetry=crystal_symmetry,
        radius=si.resolution,out=out)
      buffer=int(0.5+buffer*1.5)
    else:
      buffer=0
    lower_bounds,upper_bounds=put_bounds_in_range(
     lower_bounds=lower_bounds,upper_bounds=upper_bounds,
     box_size=box_size,buffer=buffer,
     n_real=map_data.all())

    # select map data inside this box
    print >>out,"\nSelecting map data inside box"
    box_map,box_crystal_symmetry=cut_out_map(
       map_data=map_data.as_double(),
       crystal_symmetry=crystal_symmetry,
       soft_mask=si.soft_mask,
       soft_mask_radius=si.resolution,
       resolution=si.resolution,
       shift_origin=True,
       min_point=lower_bounds, max_point=upper_bounds,out=out)
    box_pdb_inp=None

    if first_half_map_data:
      box_first_half_map,box_first_crystal_symmetry=cut_out_map(
       map_data=first_half_map_data.as_double(),
       crystal_symmetry=crystal_symmetry,
       soft_mask=si.soft_mask,
       soft_mask_radius=si.resolution,
       resolution=si.resolution,
       shift_origin=True,
       min_point=lower_bounds, max_point=upper_bounds,out=out)
    else:
      box_first_half_map=None

    if second_half_map_data:
      box_second_half_map,box_second_crystal_symmetry=cut_out_map(
       map_data=second_half_map_data.as_double(),
       crystal_symmetry=crystal_symmetry,
       soft_mask=si.soft_mask,
       soft_mask_radius=si.resolution,
       resolution=si.resolution,
       shift_origin=True,
       min_point=lower_bounds, max_point=upper_bounds,out=out)
    else:
      box_second_half_map=None

  if not box_map or (
       (not pdb_inp and not second_half_map_data) and \
      box_map.size() > max_box_fraction* map_data.size()):
    return None,map_data,first_half_map_data,\
        second_half_map_data,crystal_symmetry,None # no point

  else:
    # figure out solvent fraction in this box... 

    if get_solvent_fraction:
      box_solvent_fraction=get_iterated_solvent_fraction(
        crystal_symmetry=box_crystal_symmetry,
        map=box_map,
        out=out)
      print >>out,"Local solvent fraction: %7.2f" %(box_solvent_fraction)
    else:
      box_solvent_fraction=None

    box_sharpening_info_obj=box_sharpening_info(
      n_real=box_map.all(),
      wrapping=False,
      crystal_symmetry=box_crystal_symmetry,
      solvent_fraction=box_solvent_fraction)

    return box_pdb_inp,box_map,box_first_half_map,box_second_half_map,\
        box_crystal_symmetry,box_sharpening_info_obj

def box_from_center( si=None,
           map_data=None,
           out=sys.stdout):
    cx,cy,cz=si.crystal_symmetry.unit_cell().fractionalize(si.box_center)
    print >>out, "\nBox centered at (%7.2f,%7.2f,%7.2f) A" %(
      tuple(si.box_center))
    if cx<0 or cx>1 or cy<0 or cy>1 or cz<0 or cz>1:
       raise Sorry("Box center must be inside (0,1)")
    ax,ay,az=map_data.all()
    cgx,cgy,cgz=int(0.5+ax*cx),int(0.5+ay*cy),int(0.5+az*cz),
    print >>out,"Box grid centered at (%d,%d,%d)\n" %(cgx,cgy,cgz)
    return (cgx,cgy,cgz),(cgx,cgy,cgz)

def box_of_smallest_region(si=None,
           map_data=None,
           return_as_list=None,
           out=sys.stdout):
  return box_of_biggest_region(si=si,
           map_data=map_data,
           return_as_list=return_as_list,
           use_smallest=True,
           out=out)

def box_of_biggest_region(si=None,
           map_data=None,
           return_as_list=None,
           use_smallest=False,
           out=sys.stdout):
    n_residues=si.n_residues
    ncs_copies=si.ncs_copies
    solvent_fraction=si.solvent_fraction

    b_vs_region=b_vs_region_info()
    co,sorted_by_volume,min_b,max_b,unique_expected_regions,best_score,\
       new_threshold,starting_density_threshold=\
        get_connectivity(
           b_vs_region=b_vs_region,
           map_data=map_data,
           n_residues=n_residues,
           ncs_copies=ncs_copies,
           solvent_fraction=solvent_fraction,
           min_volume=si.min_volume,
           min_ratio=si.min_ratio,
           fraction_occupied=si.fraction_occupied,
           wrapping=si.wrapping,
           residues_per_region=si.residues_per_region,
           max_ratio_to_target=si.max_ratio_to_target,
           min_ratio_to_target=si.min_ratio_to_target,
           min_ratio_of_ncs_copy_to_first=si.min_ratio_of_ncs_copy_to_first,
           starting_density_threshold=si.starting_density_threshold,
           density_threshold=si.density_threshold,
           crystal_symmetry=si.crystal_symmetry,
           chain_type=si.chain_type,
           verbose=si.verbose,
           out=out)

    if len(sorted_by_volume)<2:
      return # nothing to do

    if use_smallest:
      small_ratio=0.25
      maximum_position_ratio=0.75
      v1,i1=sorted_by_volume[1]
      v_small=small_ratio*v1
      maximum_position_small=maximum_position_ratio*(len(sorted_by_volume)-1)+1

      best_pos=1
      ii=0
      for v,i in sorted_by_volume[1:]:
        ii+=1
        if v < v_small: continue
        if ii > maximum_position_small: continue
        best_pos=ii

      v,i=sorted_by_volume[best_pos]
      print >>out,"\nVolume of target region %d: %d grid points: "%(best_pos,v)
    else: # usual
      v,i=sorted_by_volume[1]
      print >>out,"\nVolume of largest region: %d grid points: "%(v)

    print >>out,\
    "Region %3d (%3d)  volume:%5d  X:%6d - %6d   Y:%6d - %6d  Z:%6d - %6d "%(
     1,i,v,
     min_b[i][0],max_b[i][0],
     min_b[i][1],max_b[i][1],
     min_b[i][2],max_b[i][2])

    if (not return_as_list):
      return min_b[i],max_b[i]

    else: # return a list of centers
      centers_frac=flex.vec3_double()
      a1,a2,a3=map_data.all()

      for v,i in sorted_by_volume[1:]:
        centers_frac.append(
          tuple((
          (min_b[i][0]+max_b[i][0])/(2.*a1),
          (min_b[i][1]+max_b[i][1])/(2.*a2),
          (min_b[i][2]+max_b[i][2])/(2.*a3),
               ))
                      )
      return centers_frac

def get_fft_map(n_real=None,map_coeffs=None):
    from cctbx import maptbx
    from cctbx.maptbx import crystal_gridding
    if n_real:
      cg=crystal_gridding(
        unit_cell=map_coeffs.crystal_symmetry().unit_cell(),
        space_group_info=map_coeffs.crystal_symmetry().space_group_info(),
        pre_determined_n_real=n_real)
    else:
      cg=None
    ccs=map_coeffs.crystal_symmetry()
    fft_map = map_coeffs.fft_map( resolution_factor = 0.25,
       crystal_gridding=cg,
       symmetry_flags=maptbx.use_space_group_symmetry)
    fft_map.apply_sigma_scaling()
    return fft_map

def average_from_bounds(lower,upper,grid_all=None):
  avg=[]
  for u,l in zip(upper,lower):
    avg.append(0.5*(u+l))
  if grid_all:
     avg_fract=[]
     for a,g in zip(avg,grid_all):
       avg_fract.append(a/g)
     avg=avg_fract
  return avg

def get_ncs_copies(site_cart,ncs_object=None,
   only_inside_box=None,unit_cell=None):


  ncs_group=ncs_object.ncs_groups()[0]
  from scitbx.array_family import flex
  from scitbx.matrix import col
  sites_cart_ncs=flex.vec3_double()

  for t,r in zip(ncs_group.translations_orth_inv(),
                 ncs_group.rota_matrices_inv()):

    sites_cart_ncs.append(r * col(site_cart)  + t)

  if only_inside_box: 
    assert unit_cell is not None
    sites_frac_ncs=unit_cell.fractionalize(sites_cart_ncs)
    new_sites_frac=flex.vec3_double()
    for x in sites_frac_ncs:
      if  x[0]>=0 and x[0]<=1  and \
          x[1]>=0 and x[1]<=1  and \
          x[2]>=0 and x[2]<=1:
        new_sites_frac.append(x)
    sites_cart_ncs=unit_cell.orthogonalize(new_sites_frac)
  return sites_cart_ncs


def fit_bounds_inside_box(lower,upper,box_size=None,all=None):
  # adjust bounds so upper>lower and box size is at least box_size
  new_lower=[]
  new_upper=[]
  for u,l,s,a in zip(upper,lower,box_size,all):
    ss=u-l+1
    delta=int((1+s-ss)/2) # desired increase in size, to subtract from l
    l=max(0,l-delta)
    ss=u-l+1
    delta=(s-ss) # desired increase in size, to add to u
    u=min(a-1,u+delta)
    new_lower.append(l)
    new_upper.append(u)
  return new_lower,new_upper 

def get_target_boxes(si=None,ncs_obj=None,map=None,out=sys.stdout):

  print >>out,80*"-"
  print >>out,"Getting segmented map to ID locations for sharpening"
  print >>out,80*"-"
   
  if si.input_weight_map_pickle_file:
    from libtbx import easy_pickle
    file_name=si.input_weight_map_pickle_file
    print >>out,"Loading segmentation data from %s" %(file_name)
    tracking_data=easy_pickle.load(file_name)

  else:
    args=[
        'resolution=%s' %(si.resolution),
        'seq_file=%s' %(si.seq_file),
        'auto_sharpen=False', # XXX could sharpen overall
        'write_output_maps=True',
        'add_neighbors=False',
        'density_select=False', ]
    if si.is_crystal:
      args.append("is_crystal=True")
    ncs_group_obj,remainder_ncs_group_obj,tracking_data=run(
     args,
     map_data=map.deep_copy(),
     ncs_obj=ncs_obj,
     crystal_symmetry=si.crystal_symmetry)

  if si.output_weight_map_pickle_file:
    from libtbx import easy_pickle
    file_name=os.path.join(si.output_directory,si.output_weight_map_pickle_file)
    print >>out,"Dumping segmentation data to %s" %(file_name)
    easy_pickle.dump(file_name,tracking_data)
 
  if not ncs_obj or ncs_obj.max_operators()==0:
    from mmtbx.ncs.ncs import ncs
    ncs_obj=ncs()
    ncs_obj.set_unit_ncs()

  print >>out,"Regions in this map:" 
  centers_frac=flex.vec3_double()
  upper_bounds_list=[]
  lower_bounds_list=[]
  for map_info_obj in tracking_data.output_region_map_info_list:
    lower,upper=map_info_obj.lower_upper_bounds()
    lower,upper=fit_bounds_inside_box(
      lower,upper,box_size=si.box_size,all=map.all())
    upper_bounds_list.append(upper)
    lower_bounds_list.append(lower)
    average_fract=average_from_bounds(lower,upper,grid_all=map.all())
    centers_frac.append(average_fract)
  centers_cart=si.crystal_symmetry.unit_cell().orthogonalize(centers_frac)


  #  Make ncs-related centers
  print >>out,"NCS ops:",ncs_obj.max_operators()
  centers_cart_ncs_list=[]
  for i in xrange(centers_cart.size()):
    centers_cart_ncs_list.append(get_ncs_copies(
       centers_cart[i],ncs_object=ncs_obj,only_inside_box=True,
       unit_cell=si.crystal_symmetry.unit_cell()) )

  all_cart=flex.vec3_double()
  for center_list in centers_cart_ncs_list:
    all_cart.extend(center_list)

  sharpening_centers_file=os.path.join(
      si.output_directory,"sharpening_centers.pdb")
  write_atoms(file_name=sharpening_centers_file,
    crystal_symmetry=si.crystal_symmetry,sites=centers_cart)
  ncs_sharpening_centers_file=os.path.join(
      si.output_directory,"ncs_sharpening_centers.pdb")
  write_atoms(file_name=ncs_sharpening_centers_file,
    crystal_symmetry=si.crystal_symmetry,sites=all_cart)
   
  print >>out,\
    "\nSharpening centers (matching shifted_map_file).\n\n "+\
      "Written to: \n%s \n%s\n"%(
      sharpening_centers_file,ncs_sharpening_centers_file)

  for i in xrange(centers_cart.size()):
    print >>out,"Center: %s (%7.2f,%7.2f,%7.2f)  Bounds: %s :: %s " %(
        i,centers_cart[i][0],centers_cart[i][1],centers_cart[i][2],
          str(lower_bounds_list[i]),str(upper_bounds_list[i]))

  print >>out,80*"-"
  print >>out,"Done getting segmented map to ID locations for sharpening"
  print >>out,80*"-"


  return upper_bounds_list,lower_bounds_list,\
     centers_cart_ncs_list,centers_cart,all_cart

def get_box_size(lower_bound=None,upper_bound=None):
  box_size=[]
  for lb,ub in zip(lower_bound,upper_bound):
    box_size.append(ub-lb)
  return box_size

def mean_dist_to_nearest_neighbor(all_cart):
  if all_cart.size()<2:  # nothing to check
    return None
  sum_dist=0.
  sum_n=0.
  for i in xrange(all_cart.size()):
    xyz=all_cart[i:i+1]
    others=all_cart[:i]
    others.extend(all_cart[i+1:])
    sum_dist+=get_closest_dist(xyz,others)
    sum_n+=1.
  return sum_dist/max(1.,sum_n)


def run_local_sharpening(si=None,
    auto_sharpen_methods=None,
    map=None,
    ncs_obj=None,
    half_map_data_list=None,
    pdb_inp=None,
    out=sys.stdout):
  print >>out,80*"-"
  print >>out,"Running local sharpening"
  print >>out,80*"-"

  # run auto_sharpen_map_or_map_coeffs with box_in_auto_sharpen=True and
  #   centered at different places.  Identify the places as centers of regions.
  #   Run on au of NCS and apply NCS to get remaining positions

  # Accumulate sums
  sum_weight_map=map.deep_copy()
  s = (sum_weight_map != 0)
  sum_weight_map=sum_weight_map.set_selected(s,0.0)
  sum_weight_value_map=sum_weight_map.deep_copy()
  upper_bounds_list,lower_bounds_list,\
     centers_cart_ncs_list,centers_cart,all_cart=\
     get_target_boxes(si=si,map=map,ncs_obj=ncs_obj,out=out)

  dist=mean_dist_to_nearest_neighbor(all_cart)
  if not dist:
    dist=10.
    if not si.smoothing_radius:
      print >>out,"No nearest neighbors...best to set smoothing radius"
  print >>out,"\nMean distance to nearest center is %7.2f A " %(
    dist)
  if not si.smoothing_radius:
    si.smoothing_radius=float("%.0f" %(dist*2/3))  # 10% from nearest neighbor
    print >>out,"Using %s A for smoothing radius" %(si.smoothing_radius)

  i=-1
  for ub,lb,centers_ncs_cart,center_cart in zip(
    upper_bounds_list,lower_bounds_list,centers_cart_ncs_list,centers_cart):
    i+=1

    if si.select_sharpened_map is not None and i != si.select_sharpened_map:
      continue
    map_file_name='sharpened_map_%s.ccp4' %(i)
    if si.read_sharpened_maps:
      print >>out,"\nReading sharpened map directly from %s" %(map_file_name)
      result=get_map_object(file_name=map_file_name,
        out=out)
      local_map_data=result[0]
    else:

      local_si=deepcopy(si)
      local_si.local_sharpening=False  # don't do it again
      local_si.box_size=get_box_size(lower_bound=lb,upper_bound=ub)
      local_si.box_center=center_cart
      local_si.box_in_auto_sharpen=True
      local_si.use_local_aniso=True
      print >>out,80*"+" 
      print >>out,"Getting local sharpening for box %s" %(i)
      print >>out,80*"+"
      local_si=auto_sharpen_map_or_map_coeffs(si=local_si,
        auto_sharpen_methods=auto_sharpen_methods,
        map=map,
        half_map_data_list=half_map_data_list,
        pdb_inp=pdb_inp,
        out=out)
      local_map_data=local_si.map_data

    if si.write_sharpened_maps:
      print >>out,"\nWriting sharpened map %s to %s" %(
       i,map_file_name)
      write_ccp4_map(si.crystal_symmetry,map_file_name,
         local_map_data)

    local_map_data=local_map_data.as_double()

    # Calculate weight map, max near location of centers_ncs_cart
    # U=rmsd**2
    # (b_eff=8*3.14159**2*U) 
    #  rmsd is at least distance between centers, not too much bigger than
    #  unit cell size, typically 10-20 A, 
    print >>out,"\nFall-off of local weight is 1/%6.1f A\n" %(
      si.smoothing_radius)
    u=si.smoothing_radius**2

    from cctbx import xray
    xrs,scatterers=set_up_xrs(crystal_symmetry=si.crystal_symmetry)
    unit_cell=si.crystal_symmetry.unit_cell()
    for xyz_cart in centers_ncs_cart:
      scatterers.append( xray.scatterer(scattering_type="H", label="H",
        site=unit_cell.fractionalize(xyz_cart), u=u, occupancy=1.0))
    xrs = xray.structure(xrs, scatterers=scatterers)

    f_array,phases=get_f_phases_from_map(map_data=map,
       crystal_symmetry=si.crystal_symmetry,
       d_min=si.resolution,
       d_min_ratio=si.d_min_ratio,
       out=out)

    weight_f_array=f_array.structure_factors_from_scatterers(
      algorithm = 'direct',
      xray_structure = xrs).f_calc()

    weight_map=get_map_from_map_coeffs(map_coeffs=weight_f_array,
      crystal_symmetry=si.crystal_symmetry,n_real=map.all())
    min_value=weight_map.as_1d().min_max_mean().min
    weight_map=weight_map-min_value # all positive or zero

    max_value=weight_map.as_1d().min_max_mean().max
    weight_map=weight_map/max(1.e-10,max_value)  # normalize; max=1 now
    min_value=1.e-10  # just a small value for all distances far from center
    s = (weight_map <min_value )  # make extra sure every point is above this
    weight_map=weight_map.set_selected(s,min_value)

    # increase sums
    sum_weight_map+=weight_map
    sum_weight_value_map+=weight_map*local_map_data

    print >>out,80*"+" 
    print >>out,"End of getting local sharpening for box %s" %(i)
    print >>out,80*"+"
 
  print >>out,"\nOverall map created from total of %s local maps" %(i)

  si.map_data=sum_weight_value_map/sum_weight_map

  # Get overall b_iso...
  map_coeffs_aa,map_coeffs,f_array,phases=effective_b_iso(
     map_data=si.map_data,
      resolution=si.resolution,
      d_min_ratio=si.d_min_ratio,
      crystal_symmetry=si.crystal_symmetry,
      out=out)
 
  print >>out,80*"+" 
  print >>out,"End of getting local sharpening "
  print >>out,80*"+"
  
  return si

def auto_sharpen_map_or_map_coeffs(
        si=None,
        resolution=None,        # resolution is required
        crystal_symmetry=None,  # supply crystal_symmetry and map or
        map=None,               #  map and n_real
        half_map_data_list=None,     #  two half-maps matching map
        is_crystal=None,
        map_coeffs=None,
        pdb_inp=None,
        ncs_obj=None,
        seq_file=None,
        rmsd=None,
        k_sol=None,
        b_sol=None,
        fraction_complete=None,
        n_real=None,
        solvent_content=None,
        region_weight=None,
        sa_percent=None,
        n_bins=None,
        eps=None,
        max_regions_to_test=None,
        fraction_occupied=None,
        input_weight_map_pickle_file=None,
        output_weight_map_pickle_file=None,
        read_sharpened_maps=None,
        write_sharpened_maps=None,
        select_sharpened_map=None,
        output_directory=None,
        smoothing_radius=None,
        local_sharpening=None,
        local_aniso_in_local_sharpening=None,
        use_local_aniso=None,
        auto_sharpen=None,
        box_in_auto_sharpen=None, # n_residues, ncs_copies required if not False
        use_weak_density=None,
        discard_if_worse=None, 
        n_residues=None,
        ncs_copies=None,
        box_center=None,
        remove_aniso=None,
        box_size=None,
        auto_sharpen_methods=None,
        residual_target=None,
        sharpening_target=None,
        d_min_ratio=None,
        max_box_fraction=None,
        mask_atoms=None,
        mask_atoms_atom_radius=None,
        value_outside_atoms=None,
        soft_mask=None,
        k_sharpen=None,
        search_b_min=None,
        search_b_max=None,
        search_b_n=None,
        maximum_low_b_adjusted_sa=None,
        b_iso=None, # if set, use it
        b_sharpen=None, # if set, use it
        resolution_dependent_b=None, # if set, use it
        verbose=None,
        out=sys.stdout):

    if si:  # 
      resolution=si.resolution
      crystal_symmetry=si.crystal_symmetry
      if not auto_sharpen:
        auto_sharpen=si.auto_sharpen
      if verbose is None:
        verbose=si.verbose
 
    if map_coeffs and not resolution:
       resolution=map_coeffs.d_min()
    if map_coeffs and not crystal_symmetry:
       crystal_symmetry=map_coeffs.crystal_symmetry()

    assert resolution is not None

    if map:
      return_as_map=True
    else:  # convert from structure factors to create map if necessary
      map=get_fft_map(n_real=n_real, map_coeffs=map_coeffs).real_map_unpadded()
      return_as_map=False

    # Set ncs_copies if possible
    if ncs_copies is None and ncs_obj and ncs_obj.max_operators():
      ncs_copies=ncs_obj.max_operators()
      print >>out,"Set ncs copies based on ncs_obj to %s" %(ncs_copies)

    # Determine if we are running model_sharpening
    if pdb_inp:
      auto_sharpen_methods=['model_sharpening']
    elif half_map_data_list and len(half_map_data_list)==2:
      auto_sharpen_methods=['half_map_sharpening']
    if not si:
      # Copy parameters to si (sharpening_info_object)
      si=set_up_si(var_dict=locals(),
        crystal_symmetry=crystal_symmetry,
        is_crystal=is_crystal,
        solvent_fraction=solvent_content,
        auto_sharpen=auto_sharpen,
        map=map,
        verbose=verbose,
        half_map_data_list=half_map_data_list,
        pdb_inp=pdb_inp,
        ncs_copies=ncs_copies,
        n_residues=n_residues,out=out)
    # Figure out solvent fraction
    if si.solvent_fraction is None:
      si.solvent_fraction=get_iterated_solvent_fraction(
        crystal_symmetry=crystal_symmetry,
        verbose=si.verbose,
        map=map,
        out=out)
    print >>out,"Estimated solvent fraction: %s" %(si.solvent_fraction)

    # Determine if we are running half-map or model_sharpening
    if half_map_data_list and len(half_map_data_list)==2:
      first_half_map_data=half_map_data_list[0]
      second_half_map_data=half_map_data_list[1]
    else:
      first_half_map_data=None
      second_half_map_data=None

    # Decide if we are running local sharpening (overlapping set of sharpening
    #   runs at various locations)
    if si.local_sharpening:
      return run_local_sharpening(si=si,
         auto_sharpen_methods=auto_sharpen_methods,
         map=map,
         ncs_obj=ncs_obj,
         half_map_data_list=half_map_data_list,
         pdb_inp=pdb_inp,
         out=out)

    # Now identify optimal sharpening params
    print >>out,80*"="
    print >>out,"\nRunning auto_sharpen to get sharpening parameters\n"
    print >>out,80*"="
    si=run_auto_sharpen( # get sharpening parameters standard run
      si=si,
      map_data=map,
      first_half_map_data=first_half_map_data,
      second_half_map_data=second_half_map_data,
      pdb_inp=pdb_inp,
      auto_sharpen_methods=auto_sharpen_methods,
      out=out)
    print >>out,80*"="
    print >>out,"\nDone running auto_sharpen to get sharpening parameters\n"
    print >>out,80*"="

    # Apply the optimal sharpening values and save map in si.map_data
    # First test without sharpening if sharpening_method is b_iso,b and
    # b_iso is not set
    if si.sharpening_method in [
       'b_iso','b_iso_to_d_cut','resolution_dependent'] and b_iso is None:
      local_si=deepcopy(si)
      local_si.sharpening_method='no_sharpening'
      local_si.sharpen_and_score_map(map_data=map,out=out)
      print >>out,"\nScore for no sharpening: %7.2f " %(local_si.score)
    else:
      local_si=None

    print >>out,80*"="
    print >>out,"\nApplying final sharpening to entire map"
    print >>out,80*"="
    si.sharpen_and_score_map(map_data=map,out=out)

    if discard_if_worse and local_si and local_si.score > si.score:
       print >>out,"Sharpening did not improve map "+\
        "(%7.2f sharpened, %7.2f unsharpened). Discarding sharpened map" %(
        si.score,local_si.score)
       print >>out,"\nUse discard_if_worse=False to keep the sharpening"
       local_si.sharpen_and_score_map(map_data=map,out=out)
       si=local_si 
    if not si.is_model_sharpening() and not si.is_half_map_sharpening():
      si.show_score(out=out)
      si.show_summary(out=out)

    return si  # si.map_data is the sharpened map

def run_auto_sharpen(
      si=None,
      map_data=None,
      first_half_map_data=None,
      second_half_map_data=None,
      pdb_inp=None,
      auto_sharpen_methods=None,
      out=sys.stdout):
  #  Identifies parameters for optimal map sharpening using analysis of density,
  #    model-correlation, or half-map correlation (first_half_map_data vs
  #     vs second_half_map_data).

  #  NOTE: We can apply this to any map_data (a part or whole of the map)
  #  BUT: need to update n_real if we change the part of the map!
  #  change with map data: crystal_symmetry, solvent_fraction, n_real, wrapping,

  if si.auto_sharpen and si.box_in_auto_sharpen:
    if pdb_inp:
      print >>out,"\nAuto-sharpening using model-defined box of density"
    else:
      print >>out,"\nAuto-sharpening using representative box of density"
    original_box_sharpening_info_obj=deepcopy(si)
    #write_ccp4_map(si.crystal_symmetry,'orig_map.ccp4',map_data)
    box_pdb_inp,box_map_data,box_first_half_map_data,box_second_half_map_data,\
         box_crystal_symmetry,box_sharpening_info_obj=\
       select_box_map_data(si=si,
           map_data=map_data,
           first_half_map_data=first_half_map_data,
           second_half_map_data=second_half_map_data,
           pdb_inp=pdb_inp,  # ZZZ allow smaller box and trim pdb_inp ; or supply pdb_inp that is just part of the model...
           out=out)
    #write_ccp4_map(box_crystal_symmetry,'box_map.ccp4',box_map_data)

    if box_sharpening_info_obj is None: # did not do it
      print >>out,"Box map is similar in size to entire map..."+\
         "skipping representative box of density"
      original_box_sharpening_info_obj=None
      crystal_symmetry=si.crystal_symmetry
    else:
      print >>out,"Using box map to identify optimal sharpening"
      print >>out,"Box map grid: %d  %d  %d" %(
         box_map_data.all())
      print >>out,"Box map cell: %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f  "%(
        box_crystal_symmetry.unit_cell().parameters())
      original_map_data=map_data
      original_crystal_symmetry=si.crystal_symmetry

      map_data=box_map_data
      pdb_inp=box_pdb_inp

      crystal_symmetry=box_crystal_symmetry
      if box_first_half_map_data:
        first_half_map_data=box_first_half_map_data
      if box_second_half_map_data:
        second_half_map_data=box_second_half_map_data
      # SET si for box now...
      si=deepcopy(si).update_with_box_sharpening_info(
        box_sharpening_info_obj=box_sharpening_info_obj)
  else:
    original_box_sharpening_info_obj=None
    box_sharpening_info_obj=None
    crystal_symmetry=si.crystal_symmetry

  map_coeffs_aa,map_coeffs,f_array,phases=effective_b_iso(
     map_data=map_data,
      resolution=si.resolution,
      d_min_ratio=si.d_min_ratio,
      remove_aniso=si.remove_aniso,
      crystal_symmetry=si.crystal_symmetry,
      out=out)
  original_b_iso=map_coeffs_aa.b_iso
  si.original_aniso_obj=map_coeffs_aa # set it so we can apply it later if desired

  if first_half_map_data:
    first_half_map_coeffs,dummy=get_f_phases_from_map(
          map_data=first_half_map_data,
       crystal_symmetry=si.crystal_symmetry,
       d_min=si.resolution,
       d_min_ratio=si.d_min_ratio,
       remove_aniso=si.remove_aniso,
       return_as_map_coeffs=True,
       out=out)
  else:
    first_half_map_coeffs=None

  if second_half_map_data:
    second_half_map_coeffs,dummy=get_f_phases_from_map(
      map_data=second_half_map_data,
       crystal_symmetry=si.crystal_symmetry,
       d_min=si.resolution,
       d_min_ratio=si.d_min_ratio,
       remove_aniso=si.remove_aniso,
       return_as_map_coeffs=True,
       out=out)
  else:
    second_half_map_coeffs=None

  if pdb_inp:
    # Getting model information if pdb_inp present ---------------------------
    from cctbx.maptbx.refine_sharpening import get_model_map_coeffs_normalized
    model_map_coeffs=get_model_map_coeffs_normalized(pdb_inp=pdb_inp,
       si=si,
       f_array=f_array,
       resolution=si.resolution,
       out=out)
  else:
    model_map_coeffs=None

  # Try various methods for sharpening. # XXX fix this up

  if si.maximum_low_b_adjusted_sa is not None and \
      (not si.sharpening_is_defined()) and (not si.is_model_sharpening()) \
     and (not si.is_half_map_sharpening()):
    # Make sure at highest sharpening the region_weight is high enough to
    #  give adjusted_sa of zero or less

    local_si=deepcopy(si).update_with_box_sharpening_info(
      box_sharpening_info_obj=box_sharpening_info_obj)
    b_iso=min(original_b_iso,si.search_b_min)
    local_si.b_sharpen=original_b_iso-b_iso
    local_si.b_iso=b_iso
    local_si.sharpening_target='b_iso'
    local_si.k_sharpen=0.

    local_map_data=apply_sharpening(
          f_array=f_array,phases=phases,
          sharpening_info_obj=local_si,
          crystal_symmetry=local_si.crystal_symmetry,
          out=null_out())
    local_si=score_map(map_data=local_map_data,sharpening_info_obj=local_si,
        out=null_out())
    print >>out,\
         " %6.1f     %6.1f  %5s   %7.3f  %7.3f" %(
          local_si.b_sharpen,local_si.b_iso,
           local_si.k_sharpen,local_si.adjusted_sa,local_si.kurtosis) + \
          "  %7.3f         %7.3f" %(
           local_si.sa_ratio,local_si.normalized_regions)
    if local_si.adjusted_sa > local_si.maximum_low_b_adjusted_sa: # adjust weight
      region_weight=(local_si.sa_ratio-local_si.maximum_low_b_adjusted_sa)/max(
         1.e-10,local_si.normalized_regions)
      print >>out,"\nRegion weight adjusted to %5.1f" %(region_weight)
      si.region_weight=region_weight
      

  null_si=None
  best_si=deepcopy(si).update_with_box_sharpening_info(
      box_sharpening_info_obj=box_sharpening_info_obj)
  best_map_data=None

  if si.sharpening_is_defined():  # just do it Use this if come in with method
    print >>out,"\nUsing specified sharpening"
    best_si=set_up_sharpening(si=si,map_data=map_data,out=out)
    best_si.sharpen_and_score_map(map_data=map_data,
          out=out).show_score(out=out)
    best_si.show_summary(out=out)

  else:
    if best_si.is_model_sharpening():
      print >>out,"\nSetting up model sharpening"
    elif best_si.is_half_map_sharpening():
      print >>out,"\nSetting up half-map sharpening"
    else:
      print >>out,"\nTesting sharpening methods with target of %s" %(
        best_si.sharpening_target)
    if not auto_sharpen_methods or auto_sharpen_methods==['None']:
      auto_sharpen_methods=['no_sharpening']

    for m in auto_sharpen_methods:
      # ------------------------
      if m in ['no_sharpening','resolution_dependent','model_sharpening',
          'half_map_sharpening']:
        b_min=original_b_iso
        b_max=original_b_iso
        b_n=1
        k_sharpen=0.
        delta_b=0
        if m in ['resolution_dependent','model_sharpening',
           'half_map_sharpening']:
          pass # print out later
        else:
          print >>out,\
            "\nB-sharpen   B-iso   k_sharpen   SA   "+\
             "Kurtosis  sa_ratio  Normalized regions"
      # ------------------------
      # ------------------------
      else:  #  ['b_iso','b_iso_to_d_cut']:
        if si.search_b_n>1:
          b_min=min(original_b_iso,si.search_b_min)
          b_max=max(original_b_iso,si.search_b_max)
        else: # for just one, take it
          b_min=si.search_b_min
          b_max=si.search_b_max
        b_n=si.search_b_n
        delta_b=(b_max-b_min)/max(1,b_n-1)
        print >>out,\
          "\nTesting %s with b_iso from %7.1f to %7.1f in %d steps of %7.1f" %(
          m,b_min,b_max,b_n,delta_b)
        print >>out,"(b_sharpen from %7.1f to %7.1f ) " %(
           original_b_iso-b_min,original_b_iso-b_max)
        if m=='b_iso':
          k_sharpen=0.
        else:
          k_sharpen=si.k_sharpen

        print >>out,\
            "\nB-sharpen   B-iso   k_sharpen   SA   "+\
             "Kurtosis  sa_ratio  Normalized regions"
      # ------------------------
      local_best_map_data=None
      local_best_si=deepcopy(si).update_with_box_sharpening_info(
        box_sharpening_info_obj=box_sharpening_info_obj)

      for i in xrange(b_n):
        # ============================================
        local_si=deepcopy(si).update_with_box_sharpening_info(
          box_sharpening_info_obj=box_sharpening_info_obj)
        local_si.sharpening_method=m
        local_si.n_real=map_data.all()
        local_si.k_sharpen=k_sharpen

        if m=='resolution_dependent':
          print >>out,\
           "\nRefining resolution-dependent sharpening based on %s" %(
            local_si.residual_target)
          local_si.b_sharpen=0
          local_si.b_iso=original_b_iso
          from cctbx.maptbx.refine_sharpening import run as refine_sharpening
          local_f_array,local_phases=refine_sharpening(
             map_coeffs=map_coeffs,
             sharpening_info_obj=local_si,
             out=out)
        elif m=='model_sharpening':
          print >>out,\
           "\nUsing model-based sharpening"
          local_si.b_sharpen=0
          local_si.b_iso=original_b_iso
          from cctbx.maptbx.refine_sharpening import scale_amplitudes
          scale_amplitudes(model_map_coeffs=model_map_coeffs,map_coeffs=map_coeffs,
            si=local_si,out=out)
          # local_si contains target_scale_factors now
          local_f_array=f_array
          local_phases=phases
        elif m=='half_map_sharpening':
          print >>out,\
           "\nUsing half-map-based sharpening"
          local_si.b_sharpen=0
          local_si.b_iso=original_b_iso
          from cctbx.maptbx.refine_sharpening import scale_amplitudes
          scale_amplitudes(
            map_coeffs=map_coeffs,
            first_half_map_coeffs=first_half_map_coeffs,
            second_half_map_coeffs=second_half_map_coeffs,
            si=local_si,out=out)
          # local_si contains target_scale_factors now
          local_f_array=f_array
          local_phases=phases
          
        else:
          local_f_array=f_array
          local_phases=phases
          b_iso=b_min+i*delta_b
          local_si.b_sharpen=original_b_iso-b_iso
          local_si.b_iso=b_iso

        #print >>out,"\nAbout to apply sharpening with b_iso=%6.1f A**2\n" %(b_iso)
        local_map_data=apply_sharpening(
            f_array=local_f_array,phases=local_phases,
            sharpening_info_obj=local_si,
            crystal_symmetry=local_si.crystal_symmetry,
            out=null_out())
        local_si=score_map(map_data=local_map_data,sharpening_info_obj=local_si,
          out=null_out())
        if m=='resolution_dependent':
          print >>out,\
           "\nb[0]   b[1]   b[2]   SA   Kurtosis   sa_ratio  Normalized regions"
          print >>out,\
            "\nB-sharpen   B-iso   k_sharpen   SA   "+\
             "Kurtosis  sa_ratio  Normalized regions"
          print >>out," %6.2f  %6.2f  %6.2f  " %(
              local_si.resolution_dependent_b[0],
              local_si.resolution_dependent_b[1],
              local_si.resolution_dependent_b[2]) +\
            "  %7.3f  %7.3f  " %(
                local_si.adjusted_sa,local_si.kurtosis)+\
            " %7.3f  %7.3f" %(
             local_si.sa_ratio,local_si.normalized_regions)
        elif local_si.b_sharpen is not None and local_si.b_iso is not None and\
           local_si.k_sharpen is not None and local_si.kurtosis is not None \
           and local_si.adjusted_sa is not None:
          print >>out,\
           " %6.1f     %6.1f  %5s   %7.3f  %7.3f" %(
            local_si.b_sharpen,local_si.b_iso,
             local_si.k_sharpen,local_si.adjusted_sa,local_si.kurtosis) + \
            "  %7.3f         %7.3f" %(
             local_si.sa_ratio,local_si.normalized_regions)

        if m=='no_sharpening':
          null_si=local_si
        if local_best_si.score is None or local_si.score>local_best_si.score:
          local_best_si=local_si
          local_best_map_data=local_map_data
        # ============================================


      if not local_best_si.is_model_sharpening() and \
          not local_best_si.is_half_map_sharpening():
        if local_best_si.sharpening_method=='resolution_dependent':
          print >>out,"\nBest scores for sharpening with "+\
            "b[0]=%6.2f b[1]=%6.2f b[2]=%6.2f: " %(
            local_best_si.resolution_dependent_b[0],
            local_best_si.resolution_dependent_b[1],
            local_best_si.resolution_dependent_b[2])
        else:
          print >>out,"\nBest scores for sharpening with "+\
            "b_iso=%6.1f b_sharpen=%6.1f k_sharpen=%s: " %(
            local_best_si.b_iso,local_best_si.b_sharpen,
             local_best_si.k_sharpen)

        local_best_si.show_summary(out=out)

        print >>out,\
         "Adjusted surface area: %7.3f  Kurtosis: %7.3f  Score: %7.3f\n" %(
         local_best_si.adjusted_sa,local_best_si.kurtosis,local_best_si.score)

      if best_si.score is None or local_best_si.score > best_si.score:
        best_si=local_best_si
        best_map_data=local_best_map_data
        if not best_si.is_model_sharpening() and \
            not best_si.is_half_map_sharpening():
          print >>out,"This is the current best score\n"


  if not best_si.is_model_sharpening() and not best_si.is_half_map_sharpening():
    print >>out,"\nOverall best sharpening method: %s Score: %7.3f\n" %(
       best_si.sharpening_method,best_si.score)
    best_si.show_summary(out=out)

  if (not best_si.is_model_sharpening()) and \
       (not best_si.is_half_map_sharpening()) and null_si:
    if best_si.score>null_si.score:  # we improved them..
      print >>out,"Improved score with sharpening..."
    else:
      print >>out,"Did not improve score with sharpening..."
  if original_box_sharpening_info_obj:
      # Put back original crystal_symmetry with original_box_sharpening_info_obj
      print >>out,"\nRestoring original symmetry to best sharpening info"
      best_si.update_with_box_sharpening_info(
        box_sharpening_info_obj=original_box_sharpening_info_obj)
      print >>out,"(%7.3f, %7.3f, %7.3f, %7.3f, %7.3f, %7.3f) "%(tuple(
        best_si.crystal_symmetry.unit_cell().parameters()))
      # and set tracking data with result
  return best_si

def effective_b_iso(map_data=None,tracking_data=None,
      box_sharpening_info_obj=None,
      crystal_symmetry=None,
      resolution=None,
      remove_aniso=None,
      d_min_ratio=None,
      out=sys.stdout):
    if not crystal_symmetry:
      if box_sharpening_info_obj:
        crystal_symmetry=box_sharpening_info_obj.crystal_symmetry
      else:
        crystal_symmetry=tracking_data.crystal_symmetry
    if resolution:
       d_min=resolution
    else:
       d_min=tracking_data.params.crystal_info.resolution

    if not d_min_ratio:
       d_min_ratio=tracking_data.params.map_modification.d_min_ratio

    map_coeffs,map_coeffs_ra=get_f_phases_from_map(map_data=map_data,
       crystal_symmetry=crystal_symmetry,
       d_min=d_min,
       d_min_ratio=d_min_ratio,
       remove_aniso=remove_aniso,
       return_as_map_coeffs=True,
       out=out)

    f_array,phases=map_coeffs_as_fp_phi(map_coeffs)
    b_iso=map_coeffs_ra.b_iso
    print >>out,"\nEffective B-iso = %7.2f" %(b_iso)
    return map_coeffs_ra,map_coeffs,f_array,phases

def update_tracking_data_with_sharpening(map_data=None,tracking_data=None,
       si=None,out=sys.stdout):

    # Set shifted_map_info if map_data is new
    shifted_sharpened_map_file=os.path.join(
          tracking_data.params.output_files.output_directory,
          tracking_data.params.output_files.shifted_sharpened_map_file)
    if shifted_sharpened_map_file:
      write_ccp4_map(tracking_data.crystal_symmetry,
          shifted_sharpened_map_file,map_data)
      print >>out,"Wrote shifted, sharpened map to %s" %(
          shifted_sharpened_map_file)
      tracking_data.set_shifted_map_info(file_name=
          shifted_sharpened_map_file,
          crystal_symmetry=tracking_data.crystal_symmetry,
          origin=map_data.origin(),
          all=map_data.all(),
          b_sharpen=None)

def get_one_au(tracking_data=None,
    sites_cart=None,
    ncs_obj=None,
    map_data=None,
    starting_mask=None,
    radius=None,
    every_nth_point=None,
    removed_ncs=None,
    out=sys.stdout):
  unit_cell=tracking_data.crystal_symmetry.unit_cell()

  if removed_ncs: # take everything left
    mm=map_data.as_1d().min_max_mean()
    mask_threshold=mm.min+max(0.00001,0.0001*(mm.mean-mm.min)) # just above min
  else:
    mask_threshold=tracking_data.params.segmentation.mask_threshold

  every_nth_point=tracking_data.params.segmentation.grid_spacing_for_au
  radius=tracking_data.params.segmentation.radius
  if not radius:
    radius=set_radius(unit_cell=unit_cell,map_data=map_data,
     every_nth_point=every_nth_point)
    tracking_data.params.segmentation.radius=radius
  print >>out,"\nRadius for AU identification: %7.2f A" %(radius)

  overall_mask,max_in_map,sd_map=get_overall_mask(map_data=map_data,
    mask_threshold=mask_threshold,
    crystal_symmetry=tracking_data.crystal_symmetry,
    resolution=tracking_data.params.crystal_info.resolution,
    solvent_fraction=tracking_data.solvent_fraction,
    radius=radius,
    out=out)

  if starting_mask:
    print >>out,"Points in starting mask:",starting_mask.count(True)
    print >>out,"Points in overall mask:",overall_mask.count(True)
    print >>out,"Points in both:",(starting_mask & overall_mask).count(True)
    if tracking_data.params.crystal_info.is_crystal:
      # take starting mask as overall...
      overall_mask= starting_mask
    else: # usual
      # make sure overall mask is at least as big..
      overall_mask=(overall_mask | starting_mask)
    print >>out,"New size of overall mask: ",overall_mask.count(True)
  else:
    if not sites_cart: # pick top of map
      high_points_mask=(sd_map>= 0.99*max_in_map)
      for nth_point in [4,2,1]:
        sites_cart=get_marked_points_cart(mask_data=high_points_mask,
          unit_cell=unit_cell,every_nth_point=nth_point,
          boundary_radius=radius)
        if sites_cart.size()>0: break
      assert sites_cart.size()>0
      del high_points_mask
      sites_cart=sites_cart[:1]
      xyz_frac=unit_cell.fractionalize(sites_cart[0])
      value=sd_map.value_at_closest_grid_point(xyz_frac)
      print >>out,"High point in map at (%7.2f %7.2f %7.2f) with value of %7.2f " %(
        sites_cart[0][0],sites_cart[0][1],sites_cart[0][1],value)


    starting_mask=mask_from_sites_and_map( # starting au mask
      map_data=sd_map,unit_cell=unit_cell,
      sites_cart=sites_cart,radius=radius,
      overall_mask=overall_mask)

  del sd_map

  au_mask,ncs_mask=get_ncs_mask(
    map_data=map_data,unit_cell=unit_cell,ncs_object=ncs_obj,
    starting_mask=starting_mask,
    radius=radius,
    overall_mask=overall_mask,
    every_nth_point=every_nth_point)

  print >>out,"Points in au: %d  in ncs: %d  (total %7.1f%%)   both: %d Not marked: %d" %(
     au_mask.count(True),ncs_mask.count(True),
     100.*float(au_mask.count(True)+ncs_mask.count(True))/au_mask.size(),
     (au_mask & ncs_mask).count(True),
     au_mask.size()-au_mask.count(True)-ncs_mask.count(True),)

  return au_mask

def set_up_sharpening(si=None,map_data=None,out=sys.stdout):
         print >>out,"\nCarrying out specified sharpening/blurring of map"
         check_si=si  # just use input information
         check_si.show_summary(out=out)
         if check_si.b_sharpen is None and check_si.b_iso is not None:
           # need to figure out b_sharpen
           b_iso=check_si.get_effective_b_iso(map_data=map_data,out=out)
           check_si.b_sharpen=b_iso-check_si.b_iso # sharpen is what to
           print >>out,"Value of b_sharpen to obtain b_iso of %s is %5.2f" %(
             check_si.b_iso,check_si.b_sharpen)
         elif check_si.b_sharpen is not None:
           print >>out,"Sharpening b_sharpen will be %s" %(check_si.b_sharpen)
         elif check_si.resolution_dependent_b:
           print >>out,"Resolution-dependent b_sharpening values:" +\
              "b0: %7.2f  b1: %7.2f  b2: %7.2f " %(
             tuple(check_si.resolution_dependent_b))
         elif check_si.target_scale_factors:
           print >>out,"Model sharpening scale values:"
           for x in check_si.target_scale_factors: print >>out,x,
           print >>out
         return check_si

def run(args,
     params=None,
     map_data=None,
     crystal_symmetry=None,
     half_map_data_list=None,
     ncs_obj=None,
     tracking_data=None,
     target_scattered_points=None,
     is_iteration=False,
     pdb_hierarchy=None,
     target_xyz=None,
     target_hierarchy=None,
     sharpening_target_pdb_inp=None,
     out=sys.stdout):

  if is_iteration:
    print >>out,"\nIteration tracking data:"
    tracking_data.show_summary(out=out)
  else:
    # get the parameters and map_data (magnified, shifted...)
    params,map_data,half_map_data_list,pdb_hierarchy,tracking_data=get_params(
       args,map_data=map_data,crystal_symmetry=crystal_symmetry,out=out)

    if params.input_files.pdb_to_restore:
      restore_pdb(params,tracking_data=tracking_data,out=out)
      return None,None,tracking_data
    # read and write the ncs (Normally point-group NCS)
    ncs_obj,tracking_data=get_ncs(params,tracking_data=tracking_data,
       ncs_object=ncs_obj,
       out=out)

    if params.input_files.target_ncs_au_file: # read in target
      import iotbx.pdb
      target_hierarchy=iotbx.pdb.input(
         file_name=params.input_files.target_ncs_au_file).construct_hierarchy()

    print >>out,"\nShifting map, model and NCS based on origin shift (if any)"
    print >>out,"Coordinate shift is (%7.2f,%7.2f,%7.2f)" %(
        tuple(tracking_data.origin_shift))
    if not map_data:
       raise Sorry("Need map data for segment_and_split_map")

    ncs_obj,pdb_hierarchy,target_hierarchy,\
      tracking_data,sharpening_target_pdb_inp=apply_origin_shift(
        shifted_map_file=os.path.join(
          tracking_data.params.output_files.output_directory,
          params.output_files.shifted_map_file),
        shifted_ncs_file=os.path.join(
          tracking_data.params.output_files.output_directory,
          params.output_files.shifted_ncs_file),
        shifted_pdb_file=os.path.join(
          tracking_data.params.output_files.output_directory,
          params.output_files.shifted_pdb_file),
        origin_shift=tracking_data.origin_shift,
        ncs_object=ncs_obj,
        pdb_hierarchy=pdb_hierarchy,
        target_hierarchy=target_hierarchy,
        map_data=map_data,
        tracking_data=tracking_data,
        sharpening_target_pdb_inp=sharpening_target_pdb_inp,
        out=out)

    if target_hierarchy:
      target_xyz=target_hierarchy.atoms().extract_xyz()
      del target_hierarchy

    # We can use params.input_files.target_ncs_au_file here to define ncs au
    if target_xyz and not target_scattered_points: 
       target_scattered_points=target_xyz

    # get the chain types and therefore (using ncs_copies) volume fraction
    tracking_data=get_solvent_fraction(params,
      ncs_object=ncs_obj,tracking_data=tracking_data,out=out)

    if params.map_modification.auto_sharpen or \
        params.map_modification.b_iso is not None or \
        params.map_modification.b_sharpen is not None or \
        params.map_modification.resolution_dependent_b is not None:

      # Sharpen the map
      local_params=deepcopy(params)
      local_params.crystal_info.solvent_content=tracking_data.solvent_fraction
      from cctbx.maptbx.auto_sharpen import run as auto_sharpen
      map_data=auto_sharpen(args=[],params=local_params,
        map_data=map_data,
        crystal_symmetry=tracking_data.crystal_symmetry,
        write_output_files=False,
        pdb_inp=sharpening_target_pdb_inp,
        ncs_obj=ncs_obj,
        return_map_data_only=True,
        half_map_data_list=half_map_data_list,
        n_residues=tracking_data.n_residues,
        ncs_copies=tracking_data.input_ncs_info.number_of_operators,
        out=out)

      update_tracking_data_with_sharpening(
             map_data=map_data,
             tracking_data=tracking_data,out=out)

      # done with any sharpening
      params.map_modification.auto_sharpen=False# so we don't do it again later
      params.map_modification.b_iso=None
      params.map_modification.b_sharpen=None
      params.map_modification.resolution_dependent_b=None
      if params.control.sharpen_only:
        print >>out,"Stopping after sharpening"
        return

    # Done with getting params and maps
    # Summarize after any sharpening
    tracking_data.show_summary(out=out)

  original_ncs_obj=ncs_obj # in case we need it later...
  original_input_ncs_info=tracking_data.input_ncs_info
  removed_ncs=False

  n_residues=tracking_data.n_residues
  ncs_copies=tracking_data.input_ncs_info.number_of_operators
  solvent_fraction=tracking_data.solvent_fraction


  # Now usual method, using our new map...should duplicate best result above
  for itry in xrange(2):
    # get connectivity  (conn=connectivity_object.result)
    b_vs_region=b_vs_region_info()
    si=sharpening_info(tracking_data=tracking_data)
    co,sorted_by_volume,min_b,max_b,unique_expected_regions,best_score,\
       new_threshold,starting_density_threshold=\
         get_connectivity(
           b_vs_region=b_vs_region,
           map_data=map_data,
           iterate_with_remainder=params.segmentation.iterate_with_remainder,
           n_residues=n_residues,
           ncs_copies=ncs_copies,
           solvent_fraction=solvent_fraction,
           fraction_occupied=si.fraction_occupied,
           min_volume=si.min_volume,
           min_ratio=si.min_ratio,
           wrapping=si.wrapping,
           residues_per_region=si.residues_per_region,
           max_ratio_to_target=si.max_ratio_to_target,
           min_ratio_to_target=si.min_ratio_to_target,
           min_ratio_of_ncs_copy_to_first=si.min_ratio_of_ncs_copy_to_first,
           starting_density_threshold=si.starting_density_threshold,
           density_threshold=si.density_threshold,
           crystal_symmetry=si.crystal_symmetry,
           chain_type=si.chain_type,
           verbose=si.verbose,
           out=out)
    params.segmentation.starting_density_threshold=starting_density_threshold # have to set tracking data as we are passing that above
    tracking_data.params.segmentation.starting_density_threshold=starting_density_threshold # have to set tracking data as we are passing that above
    if new_threshold:
      print >>out,"\nNew threshold is %7.2f" %(new_threshold)
    if co is None: # no luck
      return None,None,tracking_data

    # Check to see which regions are in more than one au of the NCS
    #   and set them aside.  Group ncs-related regions together

    ncs_group_obj,tracking_data,equiv_dict_ncs_copy=identify_ncs_regions(
       params,sorted_by_volume=sorted_by_volume,
       co=co,
       min_b=min_b,
       max_b=max_b,
       ncs_obj=ncs_obj,
       tracking_data=tracking_data,
       out=out)
    if ncs_group_obj and ncs_group_obj.ncs_group_list: # ok
      break
    elif ncs_obj and itry==0:# try again
      print >>out,"No NCS groups identified on first try...taking entire NCS AU."
      # Identify ncs au
      au_mask=get_one_au(tracking_data=tracking_data,
        ncs_obj=ncs_obj,
        map_data=map_data,out=out)
      s=(au_mask==False)
      min_in_map=map_data.as_1d().min_max_mean().min
      map_data.set_selected(s,min_in_map)  # mask out all but au
      from mmtbx.ncs.ncs import ncs
      ncs_obj=ncs()
      ncs_obj.set_unit_ncs()
      tracking_data.set_ncs_obj(ncs_obj=None)
      tracking_data.update_ncs_info(number_of_operators=1)
      n_residues=n_residues/ncs_copies
      solvent_fraction=max(0.001,min(0.999,
       1-((1-solvent_fraction)/ncs_copies)))
      ncs_copies=1
      params.segmentation.require_complete=False
      params.segmentation.iterate_with_remainder=False # so we do not iterate
      removed_ncs=True
      # Run again
    else: # tried twice, give up
      return None,None,tracking_data

  # Choose one region or group of regions from each ncs_group in the list
  #  Optimize the closeness of centers

  # Select group of regions that are close together and represent one au
  ncs_group_obj,scattered_points=\
     select_regions_in_au(
     params,
     ncs_group_obj=ncs_group_obj,
     equiv_dict_ncs_copy=equiv_dict_ncs_copy,
     tracking_data=tracking_data,
     target_scattered_points=target_scattered_points,
     unique_expected_regions=unique_expected_regions,
     out=out)

  # write out mask and map for all the selected regions...

  # Iterate if desired
  if params.segmentation.iterate_with_remainder and \
      ncs_group_obj.selected_regions:

    print >>out,"\nCreating remaining mask and map"
    map_data_remaining=create_remaining_mask_and_map(params,
      ncs_group_obj=ncs_group_obj,
      map_data=map_data,
      crystal_symmetry=tracking_data.crystal_symmetry,
      out=out)

    remainder_ncs_group_obj=iterate_search(params,
      map_data=map_data,
      map_data_remaining=map_data_remaining,
      ncs_obj=ncs_obj,
      ncs_group_obj=ncs_group_obj,
      scattered_points=scattered_points,
      tracking_data=tracking_data,
      out=out)
  else:
    remainder_ncs_group_obj=None

  # collect all NCS ops that are needed to relate all the regions
  #  that are used
  ncs_ops_used=ncs_group_obj.ncs_ops_used
  if remainder_ncs_group_obj and remainder_ncs_group_obj.ncs_ops_used:
    for x in remainder_ncs_group_obj.ncs_ops_used:
      if not x in ncs_ops_used: ncs_ops_used.append(x)
  if ncs_ops_used:
    ncs_ops_used.sort()
    print >>out,"Final NCS ops used: ",ncs_ops_used

  # Save the used NCS ops
  ncs_used_obj=ncs_group_obj.ncs_obj.deep_copy(ops_to_keep=ncs_ops_used) 
  shifted_used_ncs_file=os.path.join(
    tracking_data.params.output_files.output_directory,
    params.output_files.shifted_used_ncs_file)
  ncs_used_obj.format_all_for_group_specification(
         file_name=shifted_used_ncs_file)
  tracking_data.set_shifted_used_ncs_info(file_name=shifted_used_ncs_file,
    number_of_operators=ncs_used_obj.max_operators(),
    is_helical_symmetry=tracking_data.input_ncs_info.is_helical_symmetry)
  tracking_data.shifted_used_ncs_info.show_summary(out=out)

  # Write out final maps and dummy atom files
  if params.output_files.write_output_maps:
    print >>out,"\nWriting output maps"
    map_files_written=write_output_files(params,
      tracking_data=tracking_data,
      map_data=map_data,
      ncs_group_obj=ncs_group_obj,
      remainder_ncs_group_obj=remainder_ncs_group_obj,
      pdb_hierarchy=pdb_hierarchy,
      removed_ncs=removed_ncs,
      out=out)
    ncs_group_obj.set_map_files_written(map_files_written)
  else:
    map_files_written=[]

  # Restore ncs info if we removed it
  if removed_ncs:
    print >>out,"\nRestoring original NCS info to tracking_data"
    tracking_data.input_ncs_info=original_input_ncs_info


  if params.output_files.output_info_file and ncs_group_obj:
    from libtbx import easy_pickle
    tracking_data.show_summary(out=out)
    print >>out,"\nWriting summary information to: %s" %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.output_info_file))
    print >>out,\
      "\nTo restore original position of a PDB file built into these maps, use:"
    print >>out,"phenix.segment_and_split_map info_file=%s" %(
      os.path.join(tracking_data.params.output_files.output_directory,params.output_files.output_info_file))+" pdb_to_restore=mypdb.pdb\n"
    easy_pickle.dump(os.path.join(tracking_data.params.output_files.output_directory,params.output_files.output_info_file),
       tracking_data)
  return ncs_group_obj,remainder_ncs_group_obj,tracking_data


if __name__=="__main__":
  run(args=sys.argv[1:])
