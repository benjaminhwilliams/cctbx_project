#include <cctbx/boost_python/flex_fwd.h>

#include <cctbx/xray/scatterer_utils.h>
#include <cctbx/crystal/direct_space_asu.h>
#include <boost/python/class.hpp>
#include <boost/python/def.hpp>
#include <boost/python/overloads.hpp>
#include <boost/python/args.hpp>
#include <boost/python/return_value_policy.hpp>
#include <boost/python/return_by_value.hpp>

namespace cctbx { namespace xray { namespace boost_python {

namespace {

  struct scatterer_wrappers
  {
    typedef scatterer<> w_t;
    typedef w_t::float_type flt_t;

    BOOST_PYTHON_MEMBER_FUNCTION_OVERLOADS(
      apply_symmetry_1_overloads, apply_symmetry, 2, 5)

    BOOST_PYTHON_MEMBER_FUNCTION_OVERLOADS(
      apply_symmetry_2_overloads, apply_symmetry, 2, 4)

    BOOST_PYTHON_MEMBER_FUNCTION_OVERLOADS(
      apply_symmetry_u_star_overloads, apply_symmetry_u_star, 2, 3)

    static void
    wrap()
    {
      using namespace boost::python;
      typedef return_value_policy<return_by_value> rbv;
      typedef default_call_policies dcp;
      class_<w_t>("scatterer", no_init)
        .def(init<std::string const&,
                  fractional<flt_t> const&,
                  flt_t const&,
                  flt_t const&,
                  std::string const&,
                  flt_t const&,
                  flt_t const&>((
          arg_("label"),
          arg_("site"),
          arg_("u_iso"),
          arg_("occupancy"),
          arg_("scattering_type"),
          arg_("fp"),
          arg_("fdp"))))
        .def(init<std::string const&,
                  fractional<flt_t> const&,
                  scitbx::sym_mat3<flt_t> const&,
                  flt_t const&,
                  std::string const&,
                  flt_t const&,
                  flt_t const&>((
          arg_("label"),
          arg_("site"),
          arg_("u_star"),
          arg_("occupancy"),
          arg_("scattering_type"),
          arg_("fp"),
          arg_("fdp"))))
        .add_property("label", make_getter(&w_t::label, rbv()),
                               make_setter(&w_t::label, dcp()))
        .add_property("scattering_type",
          make_getter(&w_t::scattering_type, rbv()),
          make_setter(&w_t::scattering_type, dcp()))
        .add_property("fp", make_getter(&w_t::fp, rbv()),
                            make_setter(&w_t::fp, dcp()))
        .add_property("fdp", make_getter(&w_t::fdp, rbv()),
                             make_setter(&w_t::fdp, dcp()))
        .add_property("site", make_getter(&w_t::site, rbv()),
                              make_setter(&w_t::site, dcp()))
        .add_property("occupancy", make_getter(&w_t::occupancy, rbv()),
                                   make_setter(&w_t::occupancy, dcp()))
        .add_property("anisotropic_flag",
          make_getter(&w_t::anisotropic_flag, rbv()),
          make_setter(&w_t::anisotropic_flag, dcp()))
        .add_property("u_iso", make_getter(&w_t::u_iso, rbv()),
                               make_setter(&w_t::u_iso, dcp()))
        .add_property("u_star", make_getter(&w_t::u_star, rbv()),
                                make_setter(&w_t::u_star, dcp()))
        .def("is_positive_definite_u",
          (bool(w_t::*)(uctbx::unit_cell const&) const)
            &w_t::is_positive_definite_u, (
          arg_("unit_cell")))
        .def("is_positive_definite_u",
          (bool(w_t::*)(uctbx::unit_cell const&, double const&) const)
            &w_t::is_positive_definite_u, (
          arg_("unit_cell"),
          arg_("u_cart_tolerance")))
        .def("tidy_u",
          (void(w_t::*)(
            uctbx::unit_cell const&,
            sgtbx::site_symmetry_ops const&,
            double const&)) &w_t::tidy_u, (
          arg_("unit_cell"),
          arg_("site_symmetry_ops"),
          arg_("u_min")))
        .def("shift_u",
          (void(w_t::*)(
            uctbx::unit_cell const&,
            double const&)) &w_t::shift_u, (
          arg_("unit_cell"),
          arg_("u_shift")))
        .def("apply_symmetry",
          (sgtbx::site_symmetry(w_t::*)(
             uctbx::unit_cell const&,
             sgtbx::space_group const&,
             double const&,
             double const&,
             bool)) &w_t::apply_symmetry,
          apply_symmetry_1_overloads((
            arg_("unit_cell"),
            arg_("space_group"),
            arg_("min_distance_sym_equiv")=0.5,
            arg_("u_star_tolerance")=0,
            arg_("assert_min_distance_sym_equiv")=true)))
        .def("apply_symmetry",
          (void(w_t::*)(
             uctbx::unit_cell const&,
             sgtbx::site_symmetry_ops const&,
             double const&,
             bool)) &w_t::apply_symmetry,
          apply_symmetry_2_overloads((
            arg_("unit_cell"),
            arg_("site_symmetry_ops"),
            arg_("u_star_tolerance")=0,
            arg_("assert_min_distance_sym_equiv")=true)))
        .def("apply_symmetry_site", &w_t::apply_symmetry_site, (
          arg_("site_symmetry_ops")))
        .def("apply_symmetry_u_star", &w_t::apply_symmetry_u_star,
          apply_symmetry_u_star_overloads((
            arg_("unit_cell"),
            arg_("site_symmetry_ops"),
            arg_("u_star_tolerance")=0)))
        .def("multiplicity", &w_t::multiplicity)
        .def("weight_without_occupancy", &w_t::weight_without_occupancy)
        .def("weight", &w_t::weight)
      ;
    }
  };

  BOOST_PYTHON_FUNCTION_OVERLOADS(
    apply_symmetry_u_stars_overloads, apply_symmetry_u_stars, 3, 4)

} // namespace <anoymous>

  void wrap_scatterer()
  {
    using namespace boost::python;

    scatterer_wrappers::wrap();

    def("is_positive_definite_u",
      (af::shared<bool>(*)(
        af::const_ref<scatterer<> > const&,
        uctbx::unit_cell const&)) is_positive_definite_u, (
          arg_("scatterers"),
          arg_("unit_cell")));

    def("is_positive_definite_u",
      (af::shared<bool>(*)(
        af::const_ref<scatterer<> > const&,
        uctbx::unit_cell const&,
        double)) is_positive_definite_u, (
          arg_("scatterers"),
          arg_("unit_cell"),
          arg_("u_cart_tolerance")));

    def("tidy_us",
      (void(*)(
        af::ref<scatterer<> > const&,
        uctbx::unit_cell const&,
        sgtbx::site_symmetry_table const&,
        double u_min)) tidy_us, (
          arg_("scatterers"),
          arg_("unit_cell"),
          arg_("site_symmetry_table"),
          arg_("u_min")));

    def("shift_us",
      (void(*)(
        af::ref<scatterer<> > const&,
        uctbx::unit_cell const&,
        double u_min)) shift_us, (
          arg_("scatterers"),
          arg_("unit_cell"),
          arg_("u_shift")));

    def("apply_symmetry_sites",
      (void(*)(
        sgtbx::site_symmetry_table const&,
        af::ref<scatterer<> > const&)) apply_symmetry_sites, (
          arg_("site_symmetry_table"),
          arg_("scatterers")));

    def("apply_symmetry_u_stars",
      (void(*)(
        uctbx::unit_cell const&,
        sgtbx::site_symmetry_table const&,
        af::ref<scatterer<> > const&,
        double, bool, bool)) 0, apply_symmetry_u_stars_overloads((
          arg_("unit_cell"),
          arg_("site_symmetry_table"),
          arg_("scatterers"),
          arg_("u_star_tolerance")=0)));

    def("add_scatterers_ext",
      (void(*)(
        uctbx::unit_cell const&,
        sgtbx::space_group const&,
        af::ref<scatterer<> > const&,
        sgtbx::site_symmetry_table&,
        sgtbx::site_symmetry_table const&,
        double,
        double,
        bool)) add_scatterers_ext, (
          arg_("unit_cell"),
          arg_("space_group"),
          arg_("scatterers"),
          arg_("site_symmetry_table"),
          arg_("site_symmetry_table_for_new"),
          arg_("min_distance_sym_equiv"),
          arg_("u_star_tolerance"),
          arg_("assert_min_distance_sym_equiv")));

    def("change_basis",
      (af::shared<scatterer<> >(*)(
        af::const_ref<scatterer<> > const&,
        sgtbx::change_of_basis_op const&)) change_basis, (
      arg_("scatterers"), arg_("cb_op")));

    def("expand_to_p1",
      (af::shared<scatterer<> >(*)(
        uctbx::unit_cell const&,
        sgtbx::space_group const&,
        af::const_ref<scatterer<> > const&,
        sgtbx::site_symmetry_table const&,
        bool)) expand_to_p1, (
          arg_("unit_cell"),
          arg_("space_group"),
          arg_("scatterers"),
          arg_("site_symmetry_table"),
          arg_("append_number_to_labels")));

    def("n_undefined_multiplicities",
      (std::size_t(*)(
        af::const_ref<scatterer<> > const&)) n_undefined_multiplicities, (
      arg_("scatterers")));

    def("asu_mappings_process",
      (void(*)(
        crystal::direct_space_asu::asu_mappings<>&,
        af::const_ref<scatterer<> > const&,
        sgtbx::site_symmetry_table const&)) asu_mappings_process, (
      arg_("asu_mappings"), arg_("scatterers"), arg_("site_symmetry_table")));

    def("rotate",
      (af::shared<scatterer<> >(*)(
        uctbx::unit_cell const&,
        scitbx::mat3<double> const&,
        af::const_ref<scatterer<> > const&)) rotate, (
          arg_("unit_cell"),
          arg_("rotation_matrix"),
          arg_("scatterers")));
  }

}}} // namespace cctbx::xray::boost_python
