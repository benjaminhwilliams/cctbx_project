from __future__ import division

from libtbx.phil import parse
from libtbx.utils import Sorry
from xfel.ui.db.xfel_db import xfel_db_application
import sys
from xfel.ui import db_phil_str

phil_str = """
  trial = None
    .type = int
  tag = None
    .type = str
    .multiple = True
  tag_selection_mode = *union intersection
    .type = choice
"""
phil_scope = parse(phil_str + db_phil_str)

def run(args):
  user_phil = []
  for arg in args:
    try:
      user_phil.append(parse(arg))
    except Exception, e:
      raise Sorry("Unrecognized argument %s"%arg)
  params = phil_scope.fetch(sources=user_phil).extract()

  app = xfel_db_application(params)

  if params.tag is not None and len(params.tag) > 0:
    tags = []
    for tag in app.get_all_tags():
      for t in params.tag:
        if t == tag.name:
          tags.append(tag)
    extra_title = ",".join([t.name for t in tags])
  else:
    tags = None
    extra_title = None

  trial = app.get_trial(trial_number=params.trial)
  info = []
  print "Reading data..."
  cells = app.get_stats(trial=trial, tags=tags, isigi_cutoff = 1.0, tag_union = params.tag_selection_mode)()
  for cell in cells:
    info.append({'a':cell.cell_a,
                 'b':cell.cell_b,
                 'c':cell.cell_c,
                 'alpha':cell.cell_alpha,
                 'beta':cell.cell_beta,
                 'gamma':cell.cell_gamma,
                 'n_img':0})
  import xfel.ui.components.xfel_gui_plotter as pltr
  plotter = pltr.PopUpCharts()
  plotter.plot_uc_histogram(info=info, extra_title=extra_title)
  plotter.plot_uc_3Dplot(info=info)
  plotter.plt.show()

if __name__ == "__main__":
  run(sys.argv[1:])