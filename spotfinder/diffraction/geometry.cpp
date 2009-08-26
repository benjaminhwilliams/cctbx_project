#include <boost/python.hpp>
#include <scitbx/array_family/shared.h>
#include <scitbx/vec2.h>
#include <scitbx/vec3.h>
#include <scitbx/constants.h>

namespace spotfinder { namespace distltbx { namespace boost_python {

  typedef scitbx::vec3<double> point;
  typedef scitbx::af::shared<point> vec2_list;
  typedef scitbx::vec2<int> edge;
  typedef scitbx::af::shared<edge> edge_list;

  struct edge_relation {
    point left; //vector from beam to counterclockwise corner
    point right;//vector from beam to clockwise corner
    point L_R;  //vector pointing from R to L
    point nL_R; //unit vector from R to L
    point ortho;//orthogonal vector from beam to edge
    point cross;//provide a handedness reference

    edge_relation(const point& beam,
                  const point& left_corner, const point& right_corner):
      left(left_corner - beam),
      right(right_corner - beam){
      L_R  = left - right;
      nL_R = L_R.normalize();
      double Rcosq = -right * nL_R; // for parametric expression of orthogonal
      ortho = right + Rcosq*nL_R;
      cross = right.cross(left);
    }

    double magnitude(const point& a) const {
      return std::sqrt(a * a);
    }

    double edge_distance() const {
      return std::sqrt(ortho * ortho);
    }

    double operator()(const double& radius) const {
      if (radius <= edge_distance()){
        return angle_difference(right,left);
      } else {
        //find two intersection points of radius with edge; use right triangle
        double eta = std::sqrt(radius*radius - ortho * ortho);
        point etaL = ortho + eta*nL_R;
        point etaR = ortho - eta*nL_R;
        //determine if radius/edge intersection is beyond the corner
        point trueL, trueR;
        if (angle_difference(etaL, left) > 0.) {
          trueL = etaL;
        } else {
          trueL = left;
        }
        if (angle_difference(etaR, right) > 0) {
          trueR = right;
        } else {
          trueR = etaR;
        }
        return angle_difference(right,left) -
               angle_difference(trueR,trueL);
      }
    }

    double angle_difference(const point& a, const point& b) const {
      //first determine the unsigned angle
      double denominator = (magnitude(a)*magnitude(b));
      if (denominator==0.) {return 0.0;}
      double discriminant = (a * b)/denominator;
      if (discriminant>1.) {discriminant=1.;}
      if (discriminant<-1.) {discriminant=-1.;}
      double angle = std::acos(discriminant);
      //now refer the sign to the handedness reference
      if (   (cross * (a.cross(b)))   >= 0.) {
        return angle;
      } else {
        return -angle;
      }
    }
  };

  struct geometry_2d_base{
    double pixel_size, size1, size2, xbeam, ybeam, distance, wavelength;
    vec2_list corners;
    point beamspot;
    edge_list edge_index;
    scitbx::af::shared<edge_relation> edges;

    geometry_2d_base(
      const double& pixel_size,
      const double& size1,
      const double& size2,
      const double& xbeam,
      const double& ybeam,
      const double& distance,
      const double& wavelength):
      pixel_size(pixel_size),size1(size1),size2(size2),xbeam(xbeam),
      ybeam(ybeam),distance(distance),wavelength(wavelength),
      beamspot(point(xbeam,ybeam,0.)){

      corners.push_back(point(0.,              0.,0.));
      corners.push_back(point(0.,              size2*pixel_size,0.));
      corners.push_back(point(size1*pixel_size,size2*pixel_size,0.));
      corners.push_back(point(size1*pixel_size,0.,0.));

      edge_index.push_back(edge(0,1));
      edge_index.push_back(edge(1,2));
      edge_index.push_back(edge(2,3));
      edge_index.push_back(edge(3,0));

      for (int n=0; n<4; ++n){
        edges.push_back( edge_relation(beamspot,
                                       corners[edge_index[n][0]],
                                       corners[edge_index[n][1]]) );
      }
    }

    double operator()(const double& resolution) const {
      double rad = radius(resolution);
      double total_angle = 0.;
      for (int n=0; n<4; ++n) {
        double edge_contribution = edges[n](rad);
        total_angle+=edge_contribution;
      }
      return total_angle/(2.0*scitbx::constants::pi);
    }

    double radius(const double&resolution) const {
      double theta = std::asin(wavelength/2.0/resolution);
      return distance * std::tan(2.0*theta);
    }

  };

}}} // namespace spotfinder::distltbx::boost_python


namespace spotfinder { namespace distltbx { namespace boost_python {
  using namespace boost::python;
  void wrap_geometry_2d()
  {
    class_<geometry_2d_base>("geometry_2d_base", no_init)
      .def(init<const double&, const double&, const double&,
                const double&, const double&, const double&,
                const double&>(
                ( arg_("pixel_size"), arg_("size1"), arg_("size2"),
                  arg_("xbeam"), arg_("ybeam"), arg_("distance"),
                  arg_("wavelength")
                )))
      .def("__call__", &geometry_2d_base::operator())
    ;
  }

}}} // namespace spotfinder::distltbx::boost_python
