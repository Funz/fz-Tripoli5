# Jezebel: bare plutonium sphere (criticality), parameterized for fz.
# Adapted from the Jezebel example of the TRIPOLI-5 0.3.0 user guide.
#
# fz variables: radius (cm), pu239 (1/barn/cm), nb_events, nb_cycles
# Nuclear data: catalog given by the T5_CATALOG_PATH environment variable.
#
#@ import math
# Sphere volume (cm3): @{round(4 / 3 * math.pi * $radius**3, 1)}

import json
import math

import tripoli5
from tripoli5.core.euclide import Point
from tripoli5.core.literals import K, MeV
from tripoli5.core.physics import ParticleType

catalog = tripoli5.delos.Catalog.fromEnvVariable()

Pu = (
    tripoli5.materials.MixtureBuilder("concentrations")
    .withName("Pu")
    .withCatalog(catalog)
    .withTemperature(294 * K)
    .add("PU239", ${pu239~0.037047})
    .add("PU240", 0.0017512)
    .add("PU241", 0.00011674)
    .add("GA69", 0.00083603)
    .add("GA71", 0.00053917)
    .build()
)

sphere = tripoli5.agora.Sphere(Point(0.0, 0.0, 0.0), ${radius~6.39157})
jez = tripoli5.agora.Volume(tripoli5.agora.Shape(-sphere), "Pu")
bcs = tripoli5.agora.BoundaryConditions()
bcs.add(sphere, tripoli5.agora.LeakageBoundaryCondition())
geometry = tripoli5.agora.Geometry(tripoli5.agora.Universe([jez]), boundary_conditions=bcs)

media = (
    tripoli5.materials.NeutronMediumBuilder()
    .withCatalog(catalog)
    .withMixtures([Pu])
    .withURR("ace")
    .build()
)

src = tripoli5.source.PointIsotropicSource(
    ParticleType("Neutron"),
    tripoli5.distributions.energy.MonoKinetic(2.0 * MeV),
    Point(0.0, 0.0, 0.0),
)

param = tripoli5.simulation.SimulationParameters(
    nb_cycles=${nb_cycles~110},
    nb_events=${nb_events~10000},
    name="Jezebel",
    nb_threads=4,
    discard=10,
)

simu = (
    tripoli5.simulation.SimulationBuilder(
        simulation_mode="criticality", parallelism_type="openmp"
    )
    .withSource(src)
    .withGeometry(geometry)
    .withMedia("Neutron", media)
    .withParameters(param)
    .build()
)
simu.run()

# keff is also read from the log by the Tripoli5 model (outputs keff, sigma_keff);
# tripoli5_results.json returns any other quantity as the "results" output.
k = simu.getKStep()
with open("tripoli5_results.json", "w") as f:
    json.dump({"keff": float(k.mean[0]), "sigma_keff": math.sqrt(float(k.var[0]))}, f)
