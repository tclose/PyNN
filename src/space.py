# encoding: utf-8
"""
Tools for performing spatial/topographical calculations.

Classes:

  Space           - representation of a Cartesian space for use in calculating
                    distances

  Line            - represents a structure with neurons distributed evenly on a
                    straight line.
  Grid2D          - represents a structure with neurons distributed on a 2D grid.
  Grid3D          - represents a structure with neurons distributed on a 3D grid.
  RandomStructure - represents a structure with neurons distributed randomly
                    within a given volume.

  Cuboid          - representation of a cuboidal volume, for use with RandomStructure.
  Sphere          - representation of a spherical volume, for use with RandomStructure.

:copyright: Copyright 2006-2013 by the PyNN team, see AUTHORS.
:license: CeCILL, see LICENSE for details.
"""

# There must be some Python package out there that provides most of this stuff.

import numpy
import math
from operator import and_
from pyNN.random import NumpyRNG, RandomDistribution
from pyNN import descriptions
import logging

logger = logging.getLogger("PyNN")


def distance(src, tgt, mask=None, scale_factor=1.0, offset=0.0,
             periodic_boundaries=None): # may need to add an offset parameter
    """
    Return the Euclidian distance between two cells.
    `mask` allows only certain dimensions to be considered, e.g.::
      * to ignore the z-dimension, use `mask=array([0,1])`
      * to ignore y, `mask=array([0,2])`
      * to just consider z-distance, `mask=array([2])`
    `scale_factor` allows for different units in the pre- and post- position
    (the post-synaptic position is multipied by this quantity).
    """
    d = src.position - scale_factor*(tgt.position + offset)

    if not periodic_boundaries == None:
        d = numpy.minimum(abs(d), periodic_boundaries-abs(d))
    if mask is not None:
        d = d[mask]
    return numpy.sqrt(numpy.dot(d, d))


class Space(object):
    """
    Class representing a space within distances can be calculated. The space
    is Cartesian, may be 1-, 2- or 3-dimensional, and may have periodic
    boundaries in any of the dimensions.

    Arguments:
        axes:
            if not supplied, then the 3D distance is calculated. If supplied,
            axes should be a string containing the axes to be used, e.g. 'x', or
            'yz'. axes='xyz' is the same as axes=None.
        scale_factor:
            it may be that the pre and post populations use
            different units for position, e.g. degrees and µm. In this case,
            `scale_factor` can be specified, which is applied to the positions
            in the post-synaptic population.
        offset:
            if the origins of the coordinate systems of the pre- and post-
            synaptic populations are different, `offset` can be used to adjust
            for this difference. The offset is applied before any scaling.
        periodic_boundaries:
            either `None`, or a tuple giving the boundaries for each dimension,
            e.g. `((x_min, x_max), None, (z_min, z_max))`.

    """

    AXES = {'x' : [0],    'y': [1],    'z': [2],
            'xy': [0,1], 'yz': [1,2], 'xz': [0,2], 'xyz': range(3), None: range(3)}

    def __init__(self, axes=None, scale_factor=1.0, offset=0.0,
                 periodic_boundaries=None):
        """

        """
        self.periodic_boundaries = periodic_boundaries
        self.axes = numpy.array(Space.AXES[axes])
        self.scale_factor = scale_factor
        self.offset = offset

    def distances(self, A, B, expand=False):
        """
        Calculate the distance matrix between two sets of coordinates, given
        the topology of the current space.
        From http://mail.scipy.org/pipermail/numpy-discussion/2007-April/027203.html
        """
        #logger.debug("Calculating distance between A (shape=%s) and B (shape=%s)" % (A.shape, B.shape))
        if len(A.shape) == 1:
            A = A.reshape(3, 1)
        if len(B.shape) == 1:
            B = B.reshape(3, 1)
        B = self.scale_factor*(B + self.offset)
        d = numpy.zeros((len(self.axes), A.shape[1], B.shape[1]), dtype=A.dtype)
        for i,axis in enumerate(self.axes):
            diff2 = A[axis,:,None] - B[axis, :]
            if self.periodic_boundaries is not None:
                boundaries = self.periodic_boundaries[axis]
                if boundaries is not None:
                    range = boundaries[1]-boundaries[0]
                    ad2   = abs(diff2)
                    diff2 = numpy.minimum(ad2, range-ad2)
            diff2 **= 2
            d[i] = diff2
        if not expand:
            d = numpy.sum(d, 0)
        numpy.sqrt(d, d)
        return d

    def distances3D(self, A, B, expand=False):
        """
        Calculate the distance matrix between two sets of coordinates, given
        the topology of the current space.
        From http://projects.scipy.org/pipermail/numpy-discussion/2007-April/027203.html
        """
        #logger.debug("Calculating distance between A (shape=%s) and B (shape=%s)" % (A.shape, B.shape))
        assert A.shape[-1] == 3
        if len(A.shape) == 1:
            A = A.reshape(1, 3)
        if len(B.shape) == 1:
            B = B.reshape(1, 3)
        B = self.scale_factor*(B + self.offset)
        d = numpy.zeros((len(self.axes), A.shape[0], B.shape[0]), dtype=A.dtype)
        for i, axis in enumerate(self.axes):
            diff2 = A[:, None, axis] - B[:, axis]
            if self.periodic_boundaries is not None:
                boundaries = self.periodic_boundaries[axis]
                if boundaries is not None:
                    range = boundaries[1] - boundaries[0]
                    ad2   = abs(diff2)
                    diff2 = numpy.minimum(ad2, range-ad2)
            diff2 **= 2
            d[i] = diff2
        if not expand:
            d = numpy.sum(d, 0)
        numpy.sqrt(d, d)
        return d.flatten()

    def distance_generator(self, f, g):
        """
        Return a function that calculates the distance matrix as a function of
        indices i,j, given two functions f(i) and g(j) that return coordinates.
        """
        def distance_map(i, j):
            d = self.distances(f(i), g(j))
            if d.shape[0] == 1:
                d = d[0,:] # arguably this transformation should go in distances()
            elif d.shape[1] == 1:
                d = d[:,0]
            return d
        return distance_map

    def distance_generator3D(self, f, g):
        def distance_map(i, j):
            return self.distances3D(f(i), g(j))
        return distance_map


class BaseStructure(object):

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
                           ", ".join("%s=%r" % item for item in self.get_parameters().items()))

    def __eq__(self, other):
        return reduce(and_, (getattr(self, attr) == getattr(other, attr)
                             for attr in self.parameter_names))

    def get_parameters(self):
        """Return a dict containing the parameters of the :class:`Structure`."""
        P = {}
        for name in self.parameter_names:
            P[name] = getattr(self, name)
        return P

    def describe(self, template='structure_default.txt', engine='default'):
        """
        Returns a human-readable description of the network structure.

        The output may be customized by specifying a different template
        togther with an associated template engine (see ``pyNN.descriptions``).

        If template is None, then a dictionary containing the template context
        will be returned.
        """
        context = {'name': self.__class__.__name__,
                   'parameters': self.get_parameters()}
        return descriptions.render(engine, template, context)

    def generate_positions(self, n):
        """
        Calculate and return the positions of `n` neurons positioned according
        to this structure.
        """
        raise NotImplementedError


class Line(BaseStructure):
    """
    Represents a structure with neurons distributed evenly on a straight line.

    Arguments:
        `dx`:
            distance between points in the line.
        `y`, `z`,:
            y- and z-coordinates of all points in the line.
        `x0`:
            x-coordinate of the first point in the line.
    """
    parameter_names = ("dx", "x0", "y", "z")

    def __init__(self, dx=1.0, x0=0.0, y=0.0, z=0.0):
        self.dx = dx
        self.x0 = x0
        self.y = y
        self.z = z

    def generate_positions(self, n):
        x = self.dx*numpy.arange(n, dtype=float) + self.x0
        y = numpy.zeros(n) + self.y
        z = numpy.zeros(n) + self.z
        return numpy.array((x,y,z))
    generate_positions.__doc__ = BaseStructure.generate_positions.__doc__


class Grid2D(BaseStructure):
    """
    Represents a structure with neurons distributed on a 2D grid.

    Arguments:
        `dx`, `dy`:
            distances between points in the x, y directions.
        `x0`, `y0`:
            coordinates of the starting corner of the grid.
        `z`:
            the z-coordinate of all points in the grid.
        `aspect_ratio`:
            ratio of the number of grid points per side (not the ratio of the
            side lengths, unless ``dx == dy``)
        `fill_order`:
            may be 'sequential' or 'random'
    """
    parameter_names = ("aspect_ratio", "dx", "dy", "x0", "y0", "z", "fill_order")

    def __init__(self, aspect_ratio=1.0, dx=1.0, dy=1.0, x0=0.0, y0=0.0, z=0,
                 fill_order="sequential", rng=None):
        self.aspect_ratio = aspect_ratio
        assert fill_order in ('sequential', 'random')
        self.fill_order = fill_order
        self.rng = rng
        self.dx = dx; self.dy = dy; self.x0 = x0; self.y0 = y0; self.z = z

    def calculate_size(self, n):
        """docstring goes here"""
        nx = math.sqrt(n*self.aspect_ratio)
        if n%nx != 0:
            raise Exception("Invalid size: n=%g, nx=%d" % (n, nx))
        ny = n/nx
        return nx, ny

    def generate_positions(self, n):
        nx, ny = self.calculate_size(n)
        x,y,z = numpy.indices((nx,ny,1), dtype=float)
        x = self.x0 + self.dx*x.flatten()
        y = self.y0 + self.dy*y.flatten()
        z = self.z + z.flatten()
        positions = numpy.array((x,y,z)) # use column_stack, if we decide to switch from (3,n) to (n,3)
        if self.fill_order == 'sequential':
            return positions
        else: # random
            if self.rng is None:
                self.rng = NumpyRNG()
            return self.rng.permutation(positions.T).T
    generate_positions.__doc__ = BaseStructure.generate_positions.__doc__


class Grid3D(BaseStructure):
    """
    Represents a structure with neurons distributed on a 3D grid.

    Arguments:
        `dx`, `dy`, `dz`:
            distances between points in the x, y, z directions.
        `x0`, `y0`. `z0`:
            coordinates of the starting corner of the grid.
        `aspect_ratioXY`, `aspect_ratioXZ`:
            ratios of the number of grid points per side (not the ratio of the
            side lengths, unless ``dx == dy == dz``)
        `fill_order`:
            may be 'sequential' or 'random'.

    If `fill_order` is 'sequential', the z-index will be filled first, then y
    then x, i.e. the first cell will be at (0,0,0) (given default values for
    the other arguments), the second at (0,0,1), etc.
    """
    parameter_names = ("aspect_ratios", "dx", "dy", "dz", "x0", "y0", "z0", "fill_order")

    def __init__(self, aspect_ratioXY=1.0, aspect_ratioXZ=1.0, dx=1.0, dy=1.0,
                 dz=1.0, x0=0.0, y0=0.0, z0=0, fill_order="sequential", rng=None):
        self.aspect_ratios = (aspect_ratioXY, aspect_ratioXZ)
        assert fill_order in ('sequential', 'random')
        self.fill_order = fill_order
        self.rng = rng
        self.dx = dx; self.dy = dy; self.dz = dz
        self.x0 = x0; self.y0 = y0; self.z0 = z0

    def calculate_size(self, n):
        """docstring goes here"""
        a,b = self.aspect_ratios
        nx = int(round(math.pow(n*a*b, 1/3.0)))
        ny = int(round(nx/a))
        nz = int(round(nx/b))
        assert nx*ny*nz == n, str((nx, ny, nz, nx*ny*nz, n, a, b))
        return nx, ny, nz

    def generate_positions(self, n):
        nx, ny, nz = self.calculate_size(n)
        x,y,z = numpy.indices((nx,ny,nz), dtype=float)
        x = self.x0 + self.dx*x.flatten()
        y = self.y0 + self.dy*y.flatten()
        z = self.z0 + self.dz*z.flatten()
        if self.fill_order == 'sequential':
            return numpy.array((x,y,z))
        else:
            raise NotImplementedError
        generate_positions.__doc__ = BaseStructure.generate_positions.__doc__


class PerturbedGrid2D(Grid2D):
    """
    Represents a structure with neurons distributed on a 2D grid.

    Arguments:
        `dx`, `dy`:
            distances between points in the x, y directions.
        `x0`, `y0`, `z0`:
            coordinates of the starting corner of the grid.
        `perturb_x`, `perturb_y`, `perturb_z`:
            random distribution objects that independently perturb the positions on the grid
        `aspect_ratio`:
            ratio of the number of grid points per side (not the ratio of the
            side lengths, unless ``dx == dy``)
        `fill_order`:
            may be 'sequential' or 'random'
    """
    parameter_names = ("aspect_ratio", "dx", "dy", "x0", "y0", "z", "perturb_x", "perturb_y", 
                       "perturb_z", "fill_order")

    def __init__(self, aspect_ratio=1.0, dx=1.0, dy=1.0, x0=0.0, y0=0.0, z0=0, perturb_x=0, 
                 perturb_y=0, perturb_z=0, fill_order="sequential", rng=None):
        super(PerturbedGrid2D, self).__init__(aspect_ratio=aspect_ratio, dx=dx, dy=dy, x0=x0, y0=y0,
                                              z=z0, fill_order="sequential", rng=rng)
        self.perturb_x = perturb_x
        self.perturb_y = perturb_y
        self.perturb_z = perturb_z

    def generate_positions(self, n):
        positions =  super(PerturbedGrid2D, self).generate_positions(n)
        positions[dim_i,:] += self._perturbations(n)
        return positions

    def _perturbations(self, n):
        perturbations = numpy.empty(3, n)
        for dim_i, perturber in enumerate(self.perturb_x, self.perturb_y, self.perturb_z):
            if isinstance(perturber, RandomDistribution):
                perturbations[dim_i, :] = perturber.next(n, mask_local=False)
            else:
                perturbations[dim_i, :] = perturber
        return perturbations
                


class PerturbedGrid3D(Grid3D, PerturbedGrid2D):
    """
    Represents a structure with neurons distributed on a 2D grid.

    Arguments:
        `dx`, `dy`, `dz`:
            distances between points in the x, y directions.
        `x0`, `y0`, `z0`:
            coordinates of the starting corner of the grid.
        `perturb_x`, `perturb_y`, `perturb_z`:
            random distribution objects that independently perturb the positions on the grid
        `aspect_ratioXY`, `aspect_ratioXZ`:
            ratios of the number of grid points per side (not the ratio of the
            side lengths, unless ``dx == dy == dz``)
        `fill_order`:
            may be 'sequential' or 'random'
    """
    parameter_names = ("aspect_ratioXY", "aspect_ratioXZ", "dx", "dy", "dz", "x0", "y0", "z0", 
                       "perturb_x", "perturb_y", "perturb_z", "fill_order")

    def __init__(self, aspect_ratioXY=1.0, aspect_ratioXZ=1.0, dx=1.0, dy=1.0,  dz=1.0, x0=0.0, 
                 y0=0.0, z0=0, perturb_x=0, perturb_y=0, perturb_z=0, fill_order="sequential", 
                 rng=None):
        Grid3D.__init__(aspect_ratioXY=aspect_ratioXY, aspect_ratioXZ=aspect_ratioXZ, dx=dx, dy=dy, 
                        x0=x0, y0=y0, z0=z0, fill_order="sequential", rng=rng)
        self.perturb_x = perturb_x
        self.perturb_y = perturb_y
        self.perturb_z = perturb_z

    def generate_positions(self, n):
        positions =  Grid3D.generate_positions(self, n)
        positions += self._perturbations(n)
        return positions 


class Shape(object):
    pass


class Cuboid(Shape):
    """
    Represents a cuboidal volume within which neurons may be distributed.

    Arguments:
        height:
            extent in y direction
        width:
            extent in x direction
        depth:
            extent in z direction
    """

    def __init__(self, width, height, depth):
        self.height = height
        self.width = width
        self.depth = depth

    def __repr__(self):
        return "Cuboid(width=%r, height=%r, depth=%r)" % (self.width, self.height, self.depth)

    def sample(self, n, rng):
        """Return `n` points distributed randomly with uniform density within the cuboid."""
        return 0.5*rng.uniform(-1, 1, size=(n,3)) * (self.width, self.height, self.depth)


class Sphere(Shape):
    """
    Represents a spherical volume within which neurons may be distributed.
    """

    def __init__(self, radius):
        Shape.__init__(self)
        self.radius = radius

    def __repr__(self):
        return "Sphere(radius=%r)" % self.radius

    def sample(self, n, rng):
        """Return `n` points distributed randomly with uniform density within the sphere."""
        # this implementation is wasteful, as it throws away a lot of numbers,
        # but simple. More efficient implementations welcome.
        positions = numpy.empty((n,3))
        i = 0
        while i < n:
            candidate = rng.uniform(-1, 1, size=(1,3))
            if (candidate**2).sum() < 1:
                positions[i] = candidate
                i += 1
        return self.radius*positions


class RandomStructure(BaseStructure):
    """
    Represents a structure with neurons distributed randomly within a given
    volume.

    Arguments:
        `boundary` - a subclass of :class:`Shape`.
        `origin` - the coordinates (x,y,z) of the centre of the volume.
    """
    parameter_names = ('boundary', 'origin', 'rng')

    def __init__(self, boundary, origin=(0.0,0.0,0.0), rng=None):
        assert isinstance(boundary, Shape)
        assert len(origin) == 3
        self.boundary = boundary
        self.origin = origin
        self.rng = rng or NumpyRNG()

    def generate_positions(self, n):
        return (numpy.array(self.origin) + self.boundary.sample(n, self.rng)).T
    generate_positions.__doc__ = BaseStructure.generate_positions.__doc__

# what about rotations?
