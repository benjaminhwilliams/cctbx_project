from __future__ import absolute_import, division
from libtbx import test_utils
import libtbx.load_env

tst_list = (
    "$D/nanoBragg/tst_nanoBragg_minimal.py",
    )

def run () :
  build_dir = libtbx.env.under_build("simtbx")
  dist_dir = libtbx.env.dist_path("simtbx")
  test_utils.run_tests(build_dir, dist_dir, tst_list)

if (__name__ == "__main__"):
  run()
