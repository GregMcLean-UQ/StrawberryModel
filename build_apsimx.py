import json
import copy
import datetime

APSIMX_PATH = "Strawberry.apsimx"

with open(APSIMX_PATH, encoding="utf-8") as f:
    doc = json.load(f)

with open("StrawberryPhotoperiod.cs", encoding="utf-8") as f:
    photoperiod_code = f.read()

def find(node, name):
    if node.get("Name") == name:
        return node
    for c in node.get("Children", []) or []:
        r = find(c, name)
        if r:
            return r
    return None

replacements = find(doc, "Replacements")
master_plant = find(replacements, "Strawberry")

# ---- 1. Insert StrawberryPhotoperiod Script node as a child of Plant (sibling of Phenology) ----
photoperiod_script = {
    "$type": "Models.Manager, Models",
    "CodeArray": photoperiod_code.splitlines(),
    "Parameters": [
        {"Key": "CultivarType", "Value": "1"},
        {"Key": "CriticalDayLength", "Value": "14.0"},
        {"Key": "MinInductiveTemp", "Value": "8.0"},
        {"Key": "MaxInductiveTemp", "Value": "25.0"},
        {"Key": "MinInductiveDays", "Value": "10"},
        {"Key": "HeatSuppressionThreshold", "Value": "26.0"}
    ],
    "Name": "StrawberryPhotoperiod",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}

# ---- 2. Cultivars folder ----
# Albion/SanAndreas: DN, no override needed (StrawberryPhotoperiod defaults to
# CultivarType=1/DN, matching the McWhirt validation cultivars).
# GenericSD: Australian production cultivars (Qld/WA annual hill system) are
# predominantly short-day, not day-neutral. A Cultivar Command override can't
# reach a Manager script's compiled properties (confirmed empirically - and
# Replacements would stamp its one shared CultivarType default back over any
# per-simulation override anyway), so the SD/DN switch is instead handled
# inside StrawberryPhotoperiod.cs itself, keyed off Plant.CultivarName == "GenericSD".
cultivars_folder = {
    "$type": "Models.Core.Folder, Models",
    "ShowInDocs": False,
    "Name": "Cultivars",
    "ResourceName": None,
    "Children": [
        {
            "$type": "Models.PMF.Cultivar, Models",
            "Command": [],
            "Name": "Albion",
            "ResourceName": None,
            "Children": [],
            "Enabled": True,
            "ReadOnly": False
        },
        {
            "$type": "Models.PMF.Cultivar, Models",
            "Command": [],
            "Name": "SanAndreas",
            "ResourceName": None,
            "Children": [],
            "Enabled": True,
            "ReadOnly": False
        },
        {
            "$type": "Models.PMF.Cultivar, Models",
            "Command": [],
            "Name": "GenericSD",
            "ResourceName": None,
            "Children": [],
            "Enabled": True,
            "ReadOnly": False
        }
    ],
    "Enabled": True,
    "ReadOnly": False
}

mortality_rate = {
    "$type": "Models.Functions.Constant, Models",
    "FixedValue": 0.0,
    "Units": None,
    "Name": "MortalityRate",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}
seed_mortality_rate = {
    "$type": "Models.Functions.Constant, Models",
    "FixedValue": 0.0,
    "Units": None,
    "Name": "SeedMortalityRate",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}

# ---- 1b. MaturityEventPublisher - fires Plant's built-in "Harvesting" event
#      (via Harvest(removeBiomassFromOrgans: false)) the first time a
#      simulation reaches "Maturity to Harvest", for an event-triggered
#      HarvestReport (mirrors the Sorghum validation example's
#      "[Sorghum].Harvesting"-triggered HarvestReport pattern). A custom
#      Manager-declared C# event ("public event EventHandler Maturity")
#      was tried first and failed - Report could not find it via
#      "[MaturityEventPublisher].Maturity" ("Cannot find event: Maturity in
#      model", confirmed empirically) - the same underlying limitation as
#      Manager-script properties not being reliably cross-referenceable
#      seen earlier this project. Plant.Harvest() is a genuine framework
#      event so Report can subscribe to it reliably; removeBiomassFromOrgans
#      is set false specifically so this doesn't disturb the cumulative
#      multi-flush Fruit.Wt tracking the repeat-flowering loop depends on. ----
maturity_event_code = [
    "using System;",
    "using Models.Core;",
    "using Models.PMF;",
    "using Models.PMF.Phen;",
    "",
    "[Serializable]",
    "public class Script : Model",
    "{",
    "    [Link] private Plant Strawberry = null;",
    "    [Link] private Phenology Phenology = null;",
    "    private string previousPhase = \"\";",
    "    private bool hasFired = false;",
    "",
    "    [EventSubscribe(\"StartOfDay\")]",
    "    private void OnStartOfDay(object sender, EventArgs e)",
    "    {",
    "        string currentPhase = Phenology.CurrentPhaseName;",
    "        if (!hasFired && currentPhase == \"Maturity to Harvest\" && previousPhase != \"Maturity to Harvest\")",
    "        {",
    "            hasFired = true;",
    "            Strawberry.Harvest(removeBiomassFromOrgans: false);",
    "        }",
    "        previousPhase = currentPhase;",
    "    }",
    "}"
]
maturity_event_publisher = {
    "$type": "Models.Manager, Models",
    "CodeArray": maturity_event_code,
    "Parameters": [],
    "Name": "MaturityEventPublisher",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}

master_plant["Children"].append(photoperiod_script)
master_plant["Children"].append(maturity_event_publisher)
master_plant["Children"].append(cultivars_folder)
master_plant["Children"].append(mortality_rate)
master_plant["Children"].append(seed_mortality_rate)

# PhotoperiodGateValue: a plain Constant that StrawberryPhotoperiod.cs writes
# into each day, and that the phenology phase reads via VariableReference -
# this indirection exists because cross-referencing a Manager script's own
# properties by bracket-path ([StrawberryPhotoperiod].PhotoperiodGate) is not
# reliably resolvable at runtime in this APSIM build (confirmed empirically).
master_phenology = find(master_plant, "Phenology")
master_phenology["Children"].append({
    "$type": "Models.Functions.Constant, Models", "FixedValue": 1.0, "Units": None,
    "Name": "PhotoperiodGateValue", "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False
})

# ================================================================
# 3. Canopy / biomass organs - "potential growth only" (no water/N
#    stress). RUE x intercepted radiation drives daily biomass;
#    partition fractions (LMF/CMF/RMF) and HI are placeholders from
#    strawberry_parameters.xlsx pending real calibration data - see
#    Priority=High rows in that sheet's Parameters tab.
# ================================================================

def const(name, value, units=None):
    return {"$type": "Models.Functions.Constant, Models", "FixedValue": value, "Units": units,
            "Name": name, "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False}

def varref(name, path):
    return {"$type": "Models.Functions.VariableReference, Models", "VariableName": path,
            "Name": name, "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False}

def multiply(name, children):
    return {"$type": "Models.Functions.MultiplyFunction, Models", "Name": name,
            "ResourceName": None, "Children": children, "Enabled": True, "ReadOnly": False}

def divide(name, children):
    return {"$type": "Models.Functions.DivideFunction, Models", "Name": name,
            "ResourceName": None, "Children": children, "Enabled": True, "ReadOnly": False}

def phase_lookup_value(name, start, end, children):
    return {"$type": "Models.Functions.PhaseLookupValue, Models", "Start": start, "End": end,
            "Name": name, "ResourceName": None, "Children": children, "Enabled": True, "ReadOnly": False}

def phase_lookup(name, values):
    return {"$type": "Models.Functions.PhaseLookup, Models", "Name": name,
            "ResourceName": None, "Children": values, "Enabled": True, "ReadOnly": False}

def nutrient_pool_functions(name, structural, metabolic, storage):
    return {"$type": "Models.PMF.NutrientPoolFunctions, Models", "Name": name, "ResourceName": None,
            "Children": [dict(structural, Name="Structural"), dict(metabolic, Name="Metabolic"),
                         dict(storage, Name="Storage")],
            "Enabled": True, "ReadOnly": False}

def zero_n_demands(name):
    return {"$type": "Models.PMF.NutrientDemandFunctions, Models", "Name": name, "ResourceName": None,
            "Children": [const("Structural", 0.0), const("Metabolic", 0.0), const("Storage", 0.0),
                         const("QStructuralPriority", 1.0), const("QMetabolicPriority", 1.0),
                         const("QStoragePriority", 1.0)],
            "Enabled": True, "ReadOnly": False}

def partition_dm_demands(veg_fraction, fruiting_fraction):
    """DMDemands with Structural driven by a phase-dependent partition fraction of
    total plant DM supply (mirrors the Root/Stem PartitionFractionDemandFunction
    pattern in the reference Soybean model); Metabolic/Storage unused (=0)."""
    partition_fraction = phase_lookup("PartitionFraction", [
        phase_lookup_value("Vegetative", "Sowing", "FruitSet", [const("Fraction", veg_fraction)]),
        phase_lookup_value("Fruiting", "FruitSet", "Harvest", [const("Fraction", fruiting_fraction)]),
    ])
    structural = multiply("Structural", [
        {"$type": "Models.Functions.DemandFunctions.PartitionFractionDemandFunction, Models",
         "Name": "DMDemandFunction", "ResourceName": None, "Children": [partition_fraction],
         "Enabled": True, "ReadOnly": False},
        const("StructuralFraction", 1.0)
    ])
    return {"$type": "Models.PMF.NutrientDemandFunctions, Models", "Name": "DMDemands", "ResourceName": None,
            "Children": [structural, const("Metabolic", 0.0), const("Storage", 0.0),
                         const("QStructuralPriority", 1.0), const("QMetabolicPriority", 1.0),
                         const("QStoragePriority", 1.0)],
            "Enabled": True, "ReadOnly": False}

def biomass_removal_defaults(live_to_remove=0.0, dead_to_remove=0.0, live_to_residue=1.0, dead_to_residue=1.0):
    return {"$type": "Models.PMF.Library.BiomassRemoval, Models",
            "HarvestFractionLiveToRemove": live_to_remove, "HarvestFractionDeadToRemove": dead_to_remove,
            "HarvestFractionLiveToResidue": live_to_residue, "HarvestFractionDeadToResidue": dead_to_residue,
            "Name": "BiomassRemovalDefaults", "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False}

# ---- Leaf (SimpleLeaf) - canopy, RUE-driven photosynthesis ----
RUE = 1.2          # g DM/MJ, whole-plant basis - xlsx range 1.0-1.5, placeholder pending calibration
K_EXT = 0.58       # light extinction coefficient - xlsx range 0.50-0.65 (Waister et al. 1980)
SLA = 0.022        # m2/g (APSIM PMF SpecificArea convention) - literature-typical strawberry SLA, NOT in xlsx - placeholder pending calibration

leaf = {
    "$type": "Models.PMF.Organs.SimpleLeaf, Models",
    "Albedo": 0.23, "Gsmax350": 0.011, "R50": 200.0,
    "LeafInitialisationStage": "Established",
    "Height": 0.0, "BaseHeight": 0.0, "Width": 0.0, "FRGR": 0.0,
    "PotentialEP": 0.0, "WaterDemand": 0.0, "LightProfile": None,
    "KDead": 0.2, "LAIDead": 0.0,
    "Name": "Leaf", "ResourceName": None, "Enabled": True, "ReadOnly": False,
    "Children": [
        {
            "$type": "Models.Functions.SupplyFunctions.RUEModel, Models", "Name": "Photosynthesis",
            "ResourceName": None, "Enabled": True, "ReadOnly": False,
            "Children": [
                const("RUE", RUE),
                const("FT", 1.0),
                const("FVPD", 1.0),
                const("FN", 1.0),
                const("FW", 1.0),
                {"$type": "Models.Functions.SupplyFunctions.RUECO2Function, Models", "PhotosyntheticPathway": "C3",
                 "Name": "FCO2", "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False},
                varref("RadnInt", "[Leaf].RadiationIntercepted"),
            ]
        },
        multiply("FRGR", [varref("RUE_FT", "[Leaf].Photosynthesis.FT"), varref("RUE_FN", "[Leaf].Photosynthesis.FN"),
                          varref("RUE_FVPD", "[Leaf].Photosynthesis.FVPD")]),
        {"$type": "Models.Functions.SupplyFunctions.StomatalConductanceCO2Modifier, Models",
         "Name": "StomatalConductanceCO2Modifier", "ResourceName": None, "Enabled": True, "ReadOnly": False,
         "Children": [varref("PhotosynthesisCO2Modifier", "[Leaf].Photosynthesis.FCO2")]},
        multiply("Area", [varref("SLA", "[Leaf].SpecificArea"), varref("LeafLiveWt", "[Leaf].Live.Wt")]),
        const("SpecificArea", SLA, "m^2/kg"),
        const("ExtinctionCoefficient", K_EXT),
        const("HeightFunction", 150.0, "mm"),
        multiply("LAIDead", [varref("SLA", "[Leaf].SpecificArea"), varref("LeafDeadWt", "[Leaf].Dead.Wt")]),
        const("NReallocationFactor", 1.0),
        const("NRetranslocationFactor", 0.0),
        const("DMRetranslocationFactor", 0.0),
        const("DMReallocationFactor", 0.0),
        const("RemobilisationCost", 0.0),
        const("MaintenanceRespiration", 0.0),
        const("DMConversionEfficiency", 1.0, "0-1"),
        const("CarbonConcentration", 0.4),
        # Leaf turnover matters once repeat-flowering is enabled: with no
        # senescence, canopy (and therefore fruit demand, which scales off
        # AboveGroundWt) grows unbounded across successive flushes instead of
        # reaching a steady state - confirmed empirically (LAI reached >20 and
        # yield ~13-17x too high over a Nambour season before this was added).
        # ~33 day average leaf lifespan - a placeholder, not fit to data.
        # DetachmentRate stays 0 (dead leaf simply accumulates in the Dead
        # pool rather than falling to the surface) to avoid the
        # SurfaceOrganicMatter residue-type lookup crash seen earlier.
        const("SenescenceRate", 0.03, "/d"),
        const("DetachmentRate", 0.0, "/d"),
        biomass_removal_defaults(0.0, 0.0, 1.0, 1.0),
        partition_dm_demands(0.45, 0.20),  # LMF placeholder: 45% veg / 20% during fruiting
        zero_n_demands("NDemands"),
        const("InitialWt", 0.05, "g/plant"),
        const("MaximumNConc", 0.04),
        const("MinimumNConc", 0.02),
        varref("CriticalNConc", "[Leaf].MinimumNConc"),
    ]
}
# Rename the DMDemands child produced by partition_dm_demands (already "DMDemands")

# ---- Crown storage/reserve cycling (adapted from Grapevine's Cane/Trunk
#      pattern: a perennial carbohydrate reserve that fills toward a target
#      concentration during growth and can be retranslocated out via
#      DMRetranslocationFactor to support fruiting - this is the piece
#      Soybean's simple annual partitioning has no equivalent for, and the
#      main reason to prefer Grapevine as the template for Crown). ----
CROWN_MAX_STORAGE_CONC = 0.30   # g storage DM / g structural DM - placeholder (Grapevine uses 0.26 for Cane)
CROWN_DAILY_SYNTHESIS_RATE = 0.02  # /d - simplified flat rate (Grapevine uses a BetaGrowthFunction here; not adopted, to limit scope)

def crown_storage_demand():
    deficit = {
        "$type": "Models.Functions.MaximumFunction, Models", "Name": "StorageDeficit", "ResourceName": None,
        "Enabled": True, "ReadOnly": False,
        "Children": [
            {
                "$type": "Models.Functions.SubtractFunction, Models", "Name": "Deficit", "ResourceName": None,
                "Enabled": True, "ReadOnly": False,
                "Children": [
                    multiply("MaxStorage", [varref("StructuralWt", "[Crown].Live.StructuralWt"),
                                             const("MaxConcentration", CROWN_MAX_STORAGE_CONC, "gStorage/gStructural")]),
                    varref("StorageWt", "[Crown].Live.StorageWt"),
                ]
            },
            const("Zero", 0.0)
        ]
    }
    return phase_lookup("Storage", [
        phase_lookup_value("GrowingSeason", "Sowing", "Harvest", [
            multiply("Storage", [deficit, const("DailySynthesisRate", CROWN_DAILY_SYNTHESIS_RATE, "/d")])
        ])
    ])

def partition_dm_demands_with_storage(veg_fraction, fruiting_fraction, storage_fn):
    demands = partition_dm_demands(veg_fraction, fruiting_fraction)
    demands["Children"] = [c if c.get("Name") != "Storage" else dict(storage_fn, Name="Storage")
                            for c in demands["Children"]]
    return demands

# ---- Crown (GenericOrgan) - structural/storage organ ----
def generic_organ(name, dm_demands, initial_wt_g, dm_retranslocation_factor=0.0):
    return {
        "$type": "Models.PMF.Organs.GenericOrgan, Models", "IsAboveGround": name != "Root",
        "Name": name, "ResourceName": None, "Enabled": True, "ReadOnly": False,
        "Children": [
            const("Photosynthesis", 0.0),
            const("NReallocationFactor", 1.0),
            const("NRetranslocationFactor", 0.0),
            const("DMRetranslocationFactor", dm_retranslocation_factor),
            const("DMReallocationFactor", 0.0),
            const("SenescenceRate", 0.0, "/d"),
            const("DetachmentRateFunction", 0.0, "/d"),
            const("MaintenanceRespirationFunction", 0.0),
            const("DMConversionEfficiency", 1.0, "0-1"),
            const("RemobilisationCost", 0.0),
            const("CarbonConcentration", 0.4),
            biomass_removal_defaults(0.0, 0.0, 1.0, 1.0),
            dm_demands,
            zero_n_demands("NDemands"),
            nutrient_pool_functions("InitialWt", const("x", initial_wt_g, "g/plant"), const("x", 0.0), const("x", 0.0)),
            const("MaximumNConc", 0.02),
            const("MinimumNConc", 0.01),
            varref("CriticalNConc", "[%s].MinimumNConc" % name),
            varref("initialNConcFunction", "[%s].MinimumNConc" % name),
            {"$type": "Models.PMF.RetranslocateNonStructural, Models", "Name": "RetranslocateNitrogen",
             "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False},
        ]
    }

crown = generic_organ(
    "Crown",
    partition_dm_demands_with_storage(0.25, 0.15, crown_storage_demand()),  # CMF placeholder + reserve cycling
    0.05,
    dm_retranslocation_factor=0.15,  # allows stored reserves to mobilise toward fruit when supply is short
)

# Root uses the real Models.PMF.Organs.Root class (not GenericOrgan): the
# Arbitrator's WaterUptakeMethod/NitrogenUptakeMethod expect an organ that
# implements soil water/N uptake, and crash with a NullReferenceException
# if none exists in the plant - confirmed empirically. Uptake parameters
# below are generic/non-limiting placeholders (soil is deliberately generous
# and FW/FN are fixed at 1.0 in Leaf.Photosynthesis, so none of this
# actually constrains growth yet - see "potential growth only" scope note).
root = {
    "$type": "Models.PMF.Organs.Root, Models", "Name": "Root", "ResourceName": None, "Enabled": True, "ReadOnly": False,
    "Children": [
        const("RootFrontVelocity", 10.0, "mm/d"),
        const("MaximumRootDepth", 400.0, "mm"),
        {"$type": "Models.Functions.RootShape.RootShapeCylinder, Models", "Name": "RootShape", "ResourceName": None,
         "Children": [], "Enabled": True, "ReadOnly": False},
        const("KLModifier", 1.0, "0-1"),
        const("MaxDailyNUptake", 10.0, "kg/ha"),
        const("SenescenceRate", 0.005, "/d"),
        const("MaximumNConc", 0.02),
        const("MinimumNConc", 0.01),
        const("KNO3", 0.02),
        const("KNH4", 0.0),
        biomass_removal_defaults(0.0, 0.0, 1.0, 1.0),
        const("NUptakeSWFactor", 1.0),
        const("SpecificRootLength", 40.0, "m/g"),
        const("DMConversionEfficiency", 1.0, "0-1"),
        const("MaintenanceRespirationFunction", 0.0),
        const("RemobilisationCost", 0.0),
        const("CarbonConcentration", 0.4),
        partition_dm_demands(0.30, 0.15),  # RMF placeholder
        zero_n_demands("NDemands"),
        const("NReallocationFactor", 1.0),
        const("DMReallocationFactor", 0.0),
        varref("CriticalNConc", "[Root].MinimumNConc"),
        nutrient_pool_functions("InitialWt", const("x", 0.05, "g/plant"), const("x", 0.0), const("x", 0.0)),
    ]
}

# ---- Fruit (ReproductiveOrgan) - harvestable yield organ ----
# Reverted from a Grapevine-style "fruit number x BetaGrowthFunction of
# thermal time since fruit-set" demand back to a Soybean-Grain-style
# harvest-index-increase: HIGrainDemand = AboveGroundWt x (HI/FillingDuration)
# x today's ThermalTime. The Beta-growth approach saturates at a fixed
# per-flush ceiling and, critically, does not re-accumulate correctly across
# REPEATED flushes (a second FruitSet->Maturity cycle's demand never exceeds
# the first cycle's peak, since it's a delta against an accumulator that
# only ever resets to a lower value) - confirmed as the reason real Nambour
# trial yields (accumulated over ~12 sequential harvests/flushes per season)
# couldn't be reproduced. The HI-increase form uses only TODAY's thermal
# time (not a cumulative-since-event accumulator), so it naturally adds
# fresh demand on every pass through FruitSet->Maturity, however many times
# the phenology loops back through it in a season (see the GotoPhase-based
# repeat-flowering mechanism added to Phenology).
# NOTE: 0.42 (xlsx range 0.35-0.50, Bringhurst & Voth 1984) is a per-FLUSH
# harvest index; with repeat-flowering now looping through FruitSet->Maturity
# multiple times per season, that value compounds across every flush and
# overshoots the real Nambour season totals ~14-29x. Rescaled here to fit
# the average of the two observed Nambour seasons (330 g/plant 2023, 142
# g/plant 2024) - since HI is a single shared parameter, this necessarily
# sits between the two rather than matching either season exactly (the model
# still has no mechanism to know 2024 was a poorer season than 2023).
HI = 0.0095
FRUIT_WATER_CONTENT = 0.90     # fresh strawberries are ~90% water - literature typical, not in xlsx
# Filling duration matches FruitSet->GreenFruit->Maturity Wang-Engel targets
# (80 + 120 = 200 degC-d). NOTE: if those phenology targets are recalibrated,
# update this constant to match.
FILLING_DURATION = 200.0

fruit = {
    "$type": "Models.PMF.Organs.ReproductiveOrgan, Models", "GrowthRespiration": 0.0, "MaintenanceRespiration": 0.0,
    "Name": "Fruit", "ResourceName": None, "Enabled": True, "ReadOnly": False,
    "Children": [
        const("PotentialHarvestIndex", HI),
        const("FillingDuration", FILLING_DURATION, "degC-d"),
        phase_lookup("DMDemandFunction", [
            phase_lookup_value("Filling", "FruitSet", "Maturity", [
                multiply("HIFruitDemand", [
                    varref("AboveGroundWt", "[AboveGround].Wt"),
                    divide("HarvestIndexIncrease", [varref("PotentialHarvestIndex", "[Fruit].PotentialHarvestIndex"),
                                                     varref("FillingDuration", "[Fruit].FillingDuration")]),
                    varref("ThermalTime", "[Phenology].ThermalTime"),
                ])
            ])
        ]),
        const("MinimumNConc", 0.01),
        const("MaximumNConc", 0.015),
        const("WaterContent", FRUIT_WATER_CONTENT),
        divide("FreshWt", [
            varref("DryWt", "[Fruit].Wt"),
            {"$type": "Models.Functions.SubtractFunction, Models", "Name": "DryMatterFraction", "ResourceName": None,
             "Enabled": True, "ReadOnly": False,
             "Children": [const("One", 1.0), varref("WaterContent", "[Fruit].WaterContent")]}
        ]),
        multiply("NFillingRate", [varref("NConc", "[Fruit].MaximumNConc"), varref("DMDemand", "[Fruit].DMDemandFunction"),
                                   varref("DMConversionEfficiency", "[Fruit].DMConversionEfficiency")]),
        biomass_removal_defaults(1.0, 1.0, 0.0, 0.0),
        const("DMConversionEfficiency", 1.0, "0-1"),
        const("RemobilisationCost", 0.0),
        const("CarbonConcentration", 0.4),
        divide("HarvestIndex", [varref("FruitWt", "[Fruit].Wt"), varref("AboveGroundWt", "[AboveGround].Wt")]),
        const("MaximumPotentialGrainSize", 0.0),
        const("NumberFunction", 0.0),
        nutrient_pool_functions("DMDemandPriorityFactors", const("x", 1.0), const("x", 1.0), const("x", 1.0)),
        nutrient_pool_functions("NDemandPriorityFactors", const("x", 1.0), const("x", 1.0), const("x", 1.0)),
    ]
}

above_ground = {"$type": "Models.PMF.CompositeBiomass, Models", "OrganNames": ["Leaf", "Crown", "Fruit"],
                 "IncludeLive": True, "IncludeDead": True, "Name": "AboveGround", "ResourceName": None,
                 "Children": [], "Enabled": True, "ReadOnly": False}
total_biomass = {"$type": "Models.PMF.CompositeBiomass, Models", "OrganNames": ["Leaf", "Crown", "Fruit", "Root"],
                  "IncludeLive": True, "IncludeDead": True, "Name": "Total", "ResourceName": None,
                  "Children": [], "Enabled": True, "ReadOnly": False}

# ---- Arbitrator (OrganArbitrator) - verbatim structure from reference Soybean
#      model; these are generic strategy-marker classes, not strawberry-specific ----
def method(type_name, name):
    return {"$type": type_name, "Name": name, "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False}

def biomass_type_arbitrator(name, potential_methods, actual_methods, allocation_methods, extra=None):
    children = [
        {"$type": "Models.Core.Folder, Models", "ShowInDocs": True, "Name": "PotentialPartitioningMethods",
         "ResourceName": None, "Children": potential_methods, "Enabled": True, "ReadOnly": False},
        {"$type": "Models.Core.Folder, Models", "ShowInDocs": True, "Name": "AllocationMethods",
         "ResourceName": None, "Children": allocation_methods, "Enabled": True, "ReadOnly": False},
        method("Models.PMF.RelativeAllocation, Models", "ArbitrationMethod"),
    ]
    if actual_methods:
        children.insert(1, {"$type": "Models.Core.Folder, Models", "ShowInDocs": True, "Name": "ActualPartitioningMethods",
                             "ResourceName": None, "Children": actual_methods, "Enabled": True, "ReadOnly": False})
    if extra:
        children.extend(extra)
    return {"$type": "Models.PMF.BiomassTypeArbitrator, Models", "Name": name, "ResourceName": None,
            "Children": children, "Enabled": True, "ReadOnly": False}

dm_arbitration = biomass_type_arbitrator(
    "DMArbitration",
    potential_methods=[
        method("Models.PMF.Arbitrator.ReallocationMethod, Models", "ReallocationMethod"),
        method("Models.PMF.Arbitrator.AllocateFixationMethod, Models", "AllocateFixationMethod"),
        method("Models.PMF.Arbitrator.RetranslocationMethod, Models", "RetranslocationMethod"),
        method("Models.PMF.Arbitrator.SendPotentialDMAllocationsMethod, Models", "SendPotentialDMAllocationsMethod"),
    ],
    actual_methods=None,
    allocation_methods=[
        method("Models.PMF.Arbitrator.NutrientConstrainedAllocationMethod, Models", "NutrientConstrainedAllocationMethod"),
        method("Models.PMF.Arbitrator.DryMatterAllocationsMethod, Models", "DryMatterAllocationsMethod"),
    ],
)
n_arbitration = biomass_type_arbitrator(
    "NArbitration",
    potential_methods=[method("Models.PMF.Arbitrator.ReallocationMethod, Models", "ReallocationMethod")],
    actual_methods=[
        method("Models.PMF.Arbitrator.AllocateFixationMethod, Models", "AllocateFixationMethod"),
        method("Models.PMF.Arbitrator.RetranslocationMethod, Models", "RetranslocationMethod"),
    ],
    allocation_methods=[method("Models.PMF.Arbitrator.NitrogenAllocationsMethod, Models", "NitrogenAllocationsMethod")],
    extra=[method("Models.PMF.Arbitrator.AllocateUptakesMethod, Models", "AllocateUptakesMethod")],
)

arbitrator = {
    "$type": "Models.PMF.OrganArbitrator, Models", "Name": "Arbitrator", "ResourceName": None,
    "Enabled": True, "ReadOnly": False,
    "Children": [
        dm_arbitration, n_arbitration,
        method("Models.PMF.Arbitrator.WaterUptakeMethod, Models", "WaterUptakeMethod"),
        method("Models.PMF.Arbitrator.NitrogenUptakeMethod, Models", "NitrogenUptakeMethod"),
    ]
}

master_plant["Children"].extend([arbitrator, leaf, crown, root, fruit, above_ground, total_biomass])

# ================================================================
# 4. Minimal non-limiting Soil (satisfies OrganArbitrator's water/N
#    uptake link requirements; growth is NOT gated by soil moisture
#    or N since Photosynthesis's FW/FN modifiers are fixed at 1.0 -
#    see "potential growth only" scope decision).
# ================================================================

def make_soil():
    thickness = [150.0, 150.0, 150.0, 150.0]  # 600mm - shallow, strawberry-appropriate
    n = len(thickness)
    physical = {
        "$type": "Models.Soils.Physical, Models", "Thickness": thickness,
        "ParticleSizeClay": None, "ParticleSizeSand": None, "ParticleSizeSilt": None, "Rocks": None, "Texture": None,
        "BD": [1.3] * n, "AirDry": [0.10] * n, "LL15": [0.15] * n, "DUL": [0.35] * n, "SAT": [0.45] * n, "KS": None,
        "BDMetadata": None, "AirDryMetadata": None, "LL15Metadata": None, "DULMetadata": None, "SATMetadata": None,
        "KSMetadata": None, "RocksMetadata": None, "TextureMetadata": None, "ParticleSizeSandMetadata": None,
        "ParticleSizeSiltMetadata": None, "ParticleSizeClayMetadata": None,
        "Name": "Physical", "ResourceName": None, "Enabled": True, "ReadOnly": False,
        "Children": [
            {"$type": "Models.Soils.SoilCrop, Models", "LL": [0.15] * n, "KL": [0.08] * n, "XF": [1.0] * n,
             "LLMetadata": None, "KLMetadata": None, "XFMetadata": None,
             "Name": "StrawberrySoil", "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False}
        ]
    }
    soilwater = {
        "$type": "Models.WaterModel.WaterBalance, Models",
        "SummerDate": "1-Nov", "SummerU": 1.5, "SummerCona": 6.5, "WinterDate": "1-Apr", "WinterU": 1.5, "WinterCona": 6.5,
        "DiffusConst": 40.0, "DiffusSlope": 16.0, "Salb": 0.13, "CN2Bare": 73.0, "CNRed": 20.0, "CNCov": 0.8,
        "DischargeWidth": "NaN", "CatchmentArea": "NaN", "PSIDul": -100.0,
        "Thickness": thickness, "SWCON": [0.3] * n, "KLAT": None,
        "Name": "SoilWater", "ResourceName": "WaterBalance", "Enabled": True, "ReadOnly": False
    }
    organic = {
        "$type": "Models.Soils.Organic, Models", "FOMCNRatio": 40.0, "Thickness": thickness,
        "Carbon": [1.5, 0.8, 0.5, 0.4], "CarbonUnits": 0, "SoilCNRatio": [12.5] * n, "FBiom": [0.03] * n,
        "FInert": [0.4, 0.6, 0.8, 0.9], "FOM": [200.0, 120.0, 80.0, 50.0],
        "CarbonMetadata": None, "FOMMetadata": None,
        "Name": "Organic", "ResourceName": None, "Enabled": True, "ReadOnly": False
    }
    chemical = {
        "$type": "Models.Soils.Chemical, Models", "Thickness": thickness, "PH": [6.5] * n, "PHUnits": 0,
        "EC": None, "ESP": None, "CEC": None, "ECMetadata": None, "CLMetadata": None, "ESPMetadata": None, "PHMetadata": None,
        "Name": "Chemical", "ResourceName": None, "Enabled": True, "ReadOnly": False
    }
    water = {
        "$type": "Models.Soils.Water, Models", "Thickness": thickness, "InitialValues": [0.35] * n,
        "InitialPAWmm": sum((0.35 - 0.15) * t for t in thickness), "RelativeTo": "LL15", "FilledFromTop": True,
        "Name": "Water", "ResourceName": None, "Enabled": True, "ReadOnly": False
    }
    temperature = {"$type": "Models.Soils.CERESSoilTemperature, Models", "Name": "Temperature", "ResourceName": None,
                   "Enabled": True, "ReadOnly": False}

    def solute(name, initial):
        return {"$type": "Models.Soils.Solute, Models", "Thickness": thickness, "InitialValues": [initial] * n,
                "InitialValuesUnits": 0, "WaterTableConcentration": 0.0, "D0": 0.0, "Exco": None, "FIP": None,
                "DepthConstant": 0.0, "MaxDepthSoluteAccessible": 0.0, "RunoffEffectivenessAtMovingSolute": 0.0,
                "MaxEffectiveRunoff": 0.0, "Name": name, "ResourceName": None, "Enabled": True, "ReadOnly": False}

    nutrient = {"$type": "Models.Soils.Nutrients.Nutrient, Models", "Name": "Nutrient", "ResourceName": "Nutrient",
                "Enabled": True, "ReadOnly": False}

    return {
        "$type": "Models.Soils.Soil, Models", "RecordNumber": 0, "ASCOrder": None, "ASCSubOrder": None,
        "SoilType": "Generic (non-limiting)", "LocalName": None, "Site": "Strawberry generic", "NearestTown": None,
        "Region": None, "State": None, "Country": None, "NaturalVegetation": None, "ApsoilNumber": None,
        "Latitude": 0.0, "Longitude": 0.0, "LocationAccuracy": None, "YearOfSampling": None, "DataSource": None,
        "Comments": "Generic non-limiting soil - not calibrated. Water/N do not gate growth in this model version (FW=FN=1.0 in Leaf.Photosynthesis); soil exists only to satisfy OrganArbitrator's WaterUptakeMethod/NitrogenUptakeMethod link requirements.",
        "Name": "Soil", "ResourceName": None, "Enabled": True, "ReadOnly": False,
        "Children": [physical, soilwater, organic, chemical, water, temperature,
                     solute("NO3", 10.0), solute("NH4", 1.0), solute("Urea", 0.0), nutrient]
    }

# ---- 5. Build validation Simulations (Cycle1/2/3) ----
# Cycle start dates from McWhirt et al. 2023 (Agronomy 13(10):2489), Auburn AL greenhouse trial
cycles = [
    ("Cycle1_Oct25", datetime.date(2022, 10, 25), 90),
    ("Cycle2_Dec27", datetime.date(2022, 12, 27), 90),
    ("Cycle3_Feb28", datetime.date(2023, 2, 28), 90),
]

def make_plant_copy():
    # NOTE: any local edits to the Phenology subtree here get overwritten at
    # runtime by Simulations/Replacements/Strawberry (APSIM replaces any model
    # in the tree whose name+path matches a Replacements entry) - confirmed
    # empirically, so phase-skipping is done imperatively in the Sow manager
    # (SetToStage) instead of by editing Target constants in this copy.
    return copy.deepcopy(master_plant)

def make_sow_manager(cultivar_name):
    """McWhirt validation cycles: represents an already-established planting
    restarting a new flower flush, not a fresh transplant - skips straight to
    FlowerInduction (Stage 4.0) and resets canopy/biomass to an established
    plant's size (otherwise LAI starts near zero and canopy closure takes
    unrealistically long relative to what an established crown already has)."""
    code = [
        "using System;",
        "using Models.Core;",
        "using Models.PMF;",
        "using Models.PMF.Phen;",
        "using Models.PMF.Organs;",
        "",
        "[Serializable]",
        "public class Script : Model",
        "{",
        "    [Link] private Plant Strawberry = null;",
        "    [Link] private Phenology Phenology = null;",
        "    [Link] private SimpleLeaf Leaf = null;",
        "    [Link] private GenericOrgan Crown = null;",
        "    [Link] private GenericOrgan Root = null;",
        "",
        "    [Description(\"Cultivar to sow\")]",
        "    public string CultivarName { get; set; }",
        "",
        "    [EventSubscribe(\"StartOfSimulation\")]",
        "    private void OnStartOfSimulation(object sender, EventArgs e)",
        "    {",
        "        Strawberry.Sow(cultivar: CultivarName, population: 1.0, depth: 10.0, rowSpacing: 300.0);",
        "        Phenology.SetToStage(4.0);",
        "        Leaf.Live.StructuralWt = 115.0;",
        "        Crown.Live.StructuralWt = 65.0;",
        "        Root.Live.StructuralWt = 75.0;",
        "    }",
        "}"
    ]
    return {
        "$type": "Models.Manager, Models",
        "CodeArray": code,
        "Parameters": [
            {"Key": "CultivarName", "Value": cultivar_name}
        ],
        "Name": "SowStrawberry",
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

def make_transplant_manager(cultivar_name, population=1.0, row_spacing_mm=300.0):
    """Australian production run: a genuine transplant, not a flush-restart -
    runs the full phenology from Transplanting onward (no SetToStage skip).
    Starting biomass represents a real "leaf-on" nursery runner (Qld/WA
    growers plant chilled runners that already carry live leaves and a
    developed crown/root system, confirmed via industry sources), not a
    bare seedling (which stalls canopy closure for weeks under near-zero
    LAI) and not the McWhirt "already-fruiting-plant" size either.
    Population defaults to 1 plant/m2 (placeholder); pass the real commercial
    density (e.g. 5.13 plants/m2 for the Nambour trial's 51,282 plants/ha)
    when validating against per-plant yield data, since Leaf.Area/Photosynthesis
    scale total ground-area radiation capture across however many plants/m2
    are declared - simulating at 1 plant/m2 overstates per-plant biomass
    relative to a real, denser planting sharing the same intercepted radiation."""
    code = [
        "using System;",
        "using Models.Core;",
        "using Models.PMF;",
        "using Models.PMF.Organs;",
        "",
        "[Serializable]",
        "public class Script : Model",
        "{",
        "    [Link] private Plant Strawberry = null;",
        "    [Link] private SimpleLeaf Leaf = null;",
        "    [Link] private GenericOrgan Crown = null;",
        "    [Link] private GenericOrgan Root = null;",
        "",
        "    [Description(\"Cultivar to sow\")]",
        "    public string CultivarName { get; set; }",
        "    [Description(\"Population (plants/m2)\")]",
        "    public double Population { get; set; }",
        "    [Description(\"Row spacing (mm)\")]",
        "    public double RowSpacing { get; set; }",
        "",
        "    [EventSubscribe(\"StartOfSimulation\")]",
        "    private void OnStartOfSimulation(object sender, EventArgs e)",
        "    {",
        "        Strawberry.Sow(cultivar: CultivarName, population: Population, depth: 10.0, rowSpacing: RowSpacing);",
        "        Leaf.Live.StructuralWt = 8.0;",
        "        Crown.Live.StructuralWt = 5.0;",
        "        Root.Live.StructuralWt = 4.0;",
        "    }",
        "}"
    ]
    return {
        "$type": "Models.Manager, Models",
        "CodeArray": code,
        "Parameters": [
            {"Key": "CultivarName", "Value": cultivar_name},
            {"Key": "Population", "Value": str(population)},
            {"Key": "RowSpacing", "Value": str(row_spacing_mm)}
        ],
        "Name": "SowStrawberry",
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

def make_report():
    return {
        "$type": "Models.Report, Models",
        "VariableNames": [
            "[Clock].Today",
            "[Strawberry].DaysAfterSowing as DAS",
            "[Phenology].CurrentPhaseName as Phase",
            "[Phenology].CurrentStageName as StageName",
            "[Phenology].Stage as StageNumber",
            "[Phenology].AccumulatedTT as AccTT",
            "[Leaf].LAI as LAI",
            "[Leaf].Wt as LeafWt",
            "[Crown].Wt as CrownWt",
            "[Root].Wt as RootWt",
            "[Fruit].Wt as FruitWt",
            "[Crown].Live.StorageWt as CrownStorageWt",
            "[AboveGround].Wt as AboveGroundWt",
            "[Total].Wt as TotalWt"
        ],
        "EventNames": ["[Clock].EndOfDay"],
        "GroupByVariableName": None,
        "Name": "DailyReport",
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

def make_harvest_report():
    """Fires once, the first time each simulation reaches Maturity to Harvest -
    for the DaysToMaturity Predicted-vs-Observed comparison (point-in-time,
    like Sorghum's [Sorghum].Harvesting-triggered HarvestReport)."""
    return {
        "$type": "Models.Report, Models",
        "VariableNames": [
            "[Clock].Today",
            "[Strawberry].DaysAfterSowing as DAS",
        ],
        "EventNames": ["[Strawberry].Harvesting"],
        "GroupByVariableName": None,
        "Name": "HarvestReport",
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

def make_season_end_report():
    """Fires once at simulation end - for the season-total-yield Predicted-vs-
    Observed comparison (Nambour's g/plant fresh weight over the full season,
    across however many repeat flushes occurred)."""
    return {
        "$type": "Models.Report, Models",
        "VariableNames": [
            "[Clock].Today",
            "[Strawberry].DaysAfterSowing as DAS",
            "[Fruit].Wt as FruitWtDry",
            "[Fruit].FreshWt as YieldFreshGPerPlant",
        ],
        "EventNames": ["[Clock].EndOfSimulation"],
        "GroupByVariableName": None,
        "Name": "SeasonEndReport",
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

def make_surface_organic_matter():
    return {
        "$type": "Models.Surface.SurfaceOrganicMatter, Models",
        "SurfOM": [], "Canopies": [],
        "InitialResidueName": "strawberry_residue", "InitialResidueType": "wheat",
        "InitialResidueMass": 0.0, "InitialStandingFraction": 0.0, "InitialCPR": 0.0, "InitialCNR": 40.0,
        "Name": "SurfaceOrganicMatter", "ResourceName": "SurfaceOrganicMatter",
        "Enabled": True, "ReadOnly": False
    }

def make_microclimate():
    return {
        "$type": "Models.MicroClimate, Models",
        "a_interception": 0.0, "b_interception": 1.0, "c_interception": 0.0, "d_interception": 0.0,
        "SoilHeatFluxFraction": 0.4, "MinimumHeightDiffForNewLayer": 0.0, "NightInterceptionFraction": 0.5,
        "ReferenceHeight": 2.0, "Name": "MicroClimate", "ResourceName": None, "Children": [],
        "Enabled": True, "ReadOnly": False
    }

def make_zone(plant, manager):
    return {
        "$type": "Models.Core.Zone, Models",
        "Area": 1.0,
        "Slope": 0.0,
        "AspectAngle": 0.0,
        "Altitude": 50.0,
        "Name": "Field",
        "ResourceName": None,
        "Children": [make_soil(), make_surface_organic_matter(), make_microclimate(),
                     {"$type": "Models.AtmosphericPotentialEvaporation, Models", "Name": "AtmosphericPotentialEvaporation",
                      "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False},
                     plant, manager, make_report(), make_harvest_report(), make_season_end_report()],
        "Enabled": True,
        "ReadOnly": False
    }

def make_simulation(name, start_date, n_days, weather_file, manager):
    end_date = start_date + datetime.timedelta(days=n_days)
    plant = make_plant_copy()
    return {
        "$type": "Models.Core.Simulation, Models",
        "Name": name,
        "ResourceName": None,
        "Children": [
            {
                "$type": "Models.Clock, Models",
                "Start": start_date.strftime("%Y-%m-%dT00:00:00"),
                "End": end_date.strftime("%Y-%m-%dT00:00:00"),
                "Name": "Clock",
                "ResourceName": None,
                "Enabled": True,
                "ReadOnly": False
            },
            {
                "$type": "Models.Summary, Models",
                "Verbosity": 100,
                "Name": "Summary",
                "ResourceName": None,
                "Enabled": True,
                "ReadOnly": False
            },
            {
                "$type": "Models.Climate.Weather, Models",
                "ConstantsFile": None,
                "FileName": weather_file,
                "ExcelWorkSheetName": "",
                "Name": "Weather",
                "ResourceName": None,
                "Enabled": True,
                "ReadOnly": False
            },
            {
                "$type": "Models.Soils.Arbitrator.SoilArbitrator, Models",
                "Name": "SoilArbitrator",
                "ResourceName": None,
                "Enabled": True,
                "ReadOnly": False
            },
            make_zone(plant, manager)
        ],
        "Enabled": True,
        "ReadOnly": False
    }

for name, start_date, n_days in cycles:
    for cultivar in ["Albion", "SanAndreas"]:
        sim_name = f"{name}_{cultivar}"
        doc["Children"].append(make_simulation(sim_name, start_date, n_days, "Auburn_AL_2022_2023.met",
                                                make_sow_manager(cultivar)))

# ---- 6. Australian validation simulations (Nambour Qld DAF research
#      station, SD cultivar, full transplant->harvest phenology - no
#      flush-restart shortcut). Real trial data: Muir et al., Yield and
#      Fruit Weight of Six Strawberry Cultivars over Two Seasons in
#      Subtropical Queensland, Agriculture 2025, 11(3), 226 - transplant
#      dates, harvest windows, and yield below are from that paper.
#      Supersedes the earlier arbitrary-date Bundaberg placeholder run. ----
NAMBOUR_POPULATION = 51282.0 / 10000.0  # 51,282 plants/ha -> 5.1282 plants/m2 (trial's double-row density)
NAMBOUR_ROW_SPACING = 300.0             # 30 cm within rows, per the paper

nambour_seasons = [
    ("AusQld_Nambour_2023", datetime.date(2023, 3, 30), 220),  # observed: harvest 21 Jun-6 Sep 2023, yield 330 g/plant
    ("AusQld_Nambour_2024", datetime.date(2024, 4, 22), 220),  # observed: harvest 3 Jul-18 Sep 2024, yield 142 g/plant
]
for name, start_date, n_days in nambour_seasons:
    doc["Children"].append(make_simulation(
        name, start_date, n_days, "Nambour_QLD_2023_2024.met",
        make_transplant_manager("GenericSD", population=NAMBOUR_POPULATION, row_spacing_mm=NAMBOUR_ROW_SPACING),
    ))

# ================================================================
# 7. Observed-data pipeline (mirrors the Sorghum.apsimx validation
#    example): ExcelInput reads obs/Observed.xlsx into a DataStore table,
#    then two PredictedObserved merge tools join it against HarvestReport
#    (DaysToMaturity, point-in-time) and SeasonEndReport (season yield)
#    respectively, matched on SimulationName.
# ================================================================
excel_input = {
    "$type": "Models.PostSimulationTools.ExcelInput, Models",
    "FileNames": ["obs\\Observed.xlsx"],
    "SheetNames": ["Observed"],
    "Name": "ExcelInput",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}

def predicted_observed_tool(name, predicted_table):
    return {
        "$type": "Models.PostSimulationTools.PredictedObserved, Models",
        "PredictedTableName": predicted_table,
        "ObservedTableName": "Observed",
        "FieldNameUsedForMatch": "SimulationName",
        "FieldName2UsedForMatch": None,
        "FieldName3UsedForMatch": None,
        "FieldName4UsedForMatch": None,
        "AllColumns": False,
        "Name": name,
        "ResourceName": None,
        "Children": [],
        "Enabled": True,
        "ReadOnly": False
    }

post_sim_tools = {
    "$type": "Models.PostSimulationTools.ParallelPostSimulationTool, Models",
    "Name": "ParallelPostSimulationTool",
    "ResourceName": None,
    "Enabled": True,
    "ReadOnly": False,
    "Children": [
        {
            "$type": "Models.PostSimulationTools.SerialPostSimulationTool, Models",
            "Name": "PredictedObserved",
            "ResourceName": None,
            "Enabled": True,
            "ReadOnly": False,
            "Children": [
                {
                    "$type": "Models.PostSimulationTools.ParallelPostSimulationTool, Models",
                    "Name": "ReadInputs",
                    "ResourceName": None,
                    "Enabled": True,
                    "ReadOnly": False,
                    "Children": [excel_input]
                },
                {
                    "$type": "Models.PostSimulationTools.ParallelPostSimulationTool, Models",
                    "Name": "MergeWithPredictions",
                    "ResourceName": None,
                    "Enabled": True,
                    "ReadOnly": False,
                    "Children": [
                        predicted_observed_tool("DaysToMaturityPredictedObserved", "HarvestReport"),
                        predicted_observed_tool("YieldPredictedObserved", "SeasonEndReport"),
                    ]
                }
            ]
        }
    ]
}

data_store = find(doc, "DataStore")
data_store["Children"].append(post_sim_tools)

# ================================================================
# 8. Validation folder - Combined Results scatter graphs (mirrors
#    Sorghum.apsimx's "Combined Results" pattern: a single Series per
#    graph reading the merged PredictedObserved table, with a Regression
#    child providing the 1:1 line and fitted equation).
# ================================================================
def make_scatter_graph(name, table_name, field_suffix, axis_title, min_val, max_val):
    return {
        "$type": "Models.Graph, Models",
        "Axis": [
            {"$type": "APSIM.Shared.Graphing.Axis, APSIM.Shared", "Position": 3, "Title": f"Observed {axis_title}",
             "Minimum": min_val, "Maximum": max_val},
            {"$type": "APSIM.Shared.Graphing.Axis, APSIM.Shared", "Position": 0, "Title": f"Predicted {axis_title}",
             "Minimum": min_val, "Maximum": max_val},
        ],
        "LegendPosition": 3,
        "Name": name,
        "ResourceName": None,
        "Enabled": True,
        "ReadOnly": False,
        "Children": [
            {
                "$type": "Models.Series, Models",
                "Type": 1, "XAxis": 3, "YAxis": 0,
                "FactorToVaryColours": "SimulationName",
                "FactorToVaryMarkers": "SimulationName",
                "Marker": 0, "Line": 4,
                "TableName": table_name,
                "XFieldName": f"Observed.{field_suffix}",
                "YFieldName": f"Predicted.{field_suffix}",
                "ShowInLegend": True,
                "Name": "Series",
                "ResourceName": None,
                "Enabled": True,
                "ReadOnly": False,
                "Children": [
                    {"$type": "Models.Regression, Models", "ForEachSeries": False, "showOneToOne": True,
                     "showEquation": True, "Name": "Regression", "ResourceName": None, "Children": [],
                     "Enabled": True, "ReadOnly": False}
                ]
            }
        ]
    }

combined_results = {
    "$type": "Models.Core.Folder, Models", "ShowInDocs": False, "Name": "Combined Results", "ResourceName": None,
    "Enabled": True, "ReadOnly": False,
    "Children": [
        {"$type": "Models.Memo, Models", "Name": "Combined Results",
         "Text": "Predicted vs observed comparisons across all validation simulations. "
                 "DaysToMaturity: 6 McWhirt (Auburn AL, DN, greenhouse) points + 2 Nambour (Qld, SD, field) "
                 "points, the latter using the midpoint (80 d) of the paper's reported 70-90 day first-fruit "
                 "window since no exact date was published. Yield: 2 Nambour season-total points only - "
                 "McWhirt did not report yield.",
         "ResourceName": None, "Children": [], "Enabled": True, "ReadOnly": False},
        make_scatter_graph("DaysToMaturity", "DaysToMaturityPredictedObserved", "DAS", "days to maturity (d)", 0, 100),
        make_scatter_graph("Yield", "YieldPredictedObserved", "YieldFreshGPerPlant", "yield (g fresh/plant)", 0, 400),
    ]
}

# ================================================================
# 9. Per-simulation GraphPanel (mirrors Sorghum.apsimx's "PredictedObserved"
#    GraphPanel: one tab per simulation, each showing a grid of time-series
#    graphs). Our DailyReport has no observed counterpart (McWhirt/
#    Nambour publish only single point values, not daily time series), so
#    these panels show Predicted-only trajectories - still useful for
#    visually inspecting each simulation's canopy/fruit development shape,
#    just not a like-for-like Predicted-vs-Observed daily comparison the
#    way Sorghum's Biomass/LAI panels are.
# ================================================================
graph_panel_config_code = [
    "using System;",
    "using System.Linq;",
    "using System.Collections.Generic;",
    "using Models.Core;",
    "using Models.Core.Run;",
    "using Models.Storage;",
    "using Models;",
    "",
    "[Serializable]",
    "public class Script : Model, IGraphPanelScript",
    "{",
    "    public string[] GetSimulationNames(IStorageReader reader, GraphPanel panel)",
    "    {",
    "        List<ISimulationDescriptionGenerator> runnables = Node.FindAll<ISimulationDescriptionGenerator>().ToList();",
    "        runnables.RemoveAll(r => r is Simulation && (r as Simulation).Parent is Models.Factorial.Experiment);",
    "        return runnables.SelectMany(r => r.GenerateSimulationDescriptions().Select(d => d.Name)).ToArray();",
    "    }",
    "",
    "    public void TransformGraph(Graph graph, string simulationName) { }",
    "}"
]
graph_panel_config = {
    "$type": "Models.Manager, Models",
    "CodeArray": graph_panel_config_code,
    "Parameters": [],
    "Name": "Config",
    "ResourceName": None,
    "Children": [],
    "Enabled": True,
    "ReadOnly": False
}

def make_timeseries_graph(name, field_name, y_title):
    return {
        "$type": "Models.Graph, Models",
        "Axis": [
            {"$type": "APSIM.Shared.Graphing.Axis, APSIM.Shared", "Position": 3, "Title": "Date"},
            {"$type": "APSIM.Shared.Graphing.Axis, APSIM.Shared", "Position": 0, "Title": y_title},
        ],
        "LegendPosition": 3,
        "Name": name,
        "ResourceName": None,
        "Enabled": True,
        "ReadOnly": False,
        "Children": [
            {
                "$type": "Models.Series, Models",
                "Type": 1, "XAxis": 3, "YAxis": 0,
                "Marker": 11, "Line": 1,
                "TableName": "DailyReport",
                "XFieldName": "Clock.Today",
                "YFieldName": field_name,
                "ShowInLegend": False,
                "Name": "Predicted",
                "ResourceName": None,
                "Children": [],
                "Enabled": True,
                "ReadOnly": False
            }
        ]
    }

graph_panel = {
    "$type": "Models.GraphPanel, Models",
    "HideTitles": False, "FontSize": 14.0, "MarkerSize": 2, "SameXAxes": False, "SameYAxes": False,
    "LegendOutsideGraph": True, "LegendPosition": 7, "LegendOrientation": 2, "NumCols": 2,
    "Name": "PerSimulation", "ResourceName": None, "Enabled": True, "ReadOnly": False,
    "Children": [
        graph_panel_config,
        make_timeseries_graph("LAI", "LAI", "LAI (m2/m2)"),
        make_timeseries_graph("FruitWt", "FruitWt", "Fruit dry weight (g/plant)"),
        make_timeseries_graph("LeafWt", "LeafWt", "Leaf dry weight (g/plant)"),
        make_timeseries_graph("AboveGroundWt", "AboveGroundWt", "Above-ground dry weight (g/plant)"),
        make_timeseries_graph("Stage", "StageNumber", "Phenology stage"),
    ]
}

validation_folder = {
    "$type": "Models.Core.Folder, Models", "ShowInDocs": False, "Name": "Validation", "ResourceName": None,
    "Enabled": True, "ReadOnly": False,
    "Children": [combined_results, graph_panel]
}
doc["Children"].append(validation_folder)

with open(APSIMX_PATH, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2)

print("Done. Top-level children:", [c.get("Name") for c in doc["Children"]])
