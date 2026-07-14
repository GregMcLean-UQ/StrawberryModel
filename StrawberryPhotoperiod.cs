// ============================================================
// StrawberryPhotoperiod.cs
// APSIM NextGen Script Node — Photoperiod Flower Induction Gate
//
// Place this Script node as a child of [Plant].
// Name the node: StrawberryPhotoperiod
//
// Exposes:
//   [StrawberryPhotoperiod].PhotoperiodGate
//     = 1 when flowering can proceed, 0 when blocked
//
//   [StrawberryPhotoperiod].InductiveDaysAccumulated
//     = count of consecutive inductive days
//
// Logic:
//   SD cultivars (CultivarType = 0):
//     Gate = 1 ONLY when:
//       - Daylength < CriticalDayLength (typically 14 h)
//       - Mean temperature within inductive range
//         (MinInductiveTemp < Tmean < MaxInductiveTemp)
//       - InductiveDaysAccumulated >= MinInductiveDays
//     Otherwise Gate = 0 (blocks Progression in phenology phase)
//
//   DN cultivars (CultivarType = 1):
//     Gate is always 1 (photoperiod-insensitive).
//     High-temperature suppression is applied instead:
//       Gate = 1 when Tmean < HeatSuppressionThreshold (26 °C)
//       Gate = 0 when Tmean >= HeatSuppressionThreshold
//     This reflects the well-documented heat-induced flowering
//     suppression in DN cultivars above ~26 °C.
//
// Daylength is computed from latitude (read from Weather node)
// using the standard astronomical formula.
//
// Reference:
//   Resh (1998); Durner et al. (1984) flower induction thresholds
//   Hancock (1999) strawberry physiology review
// ============================================================

using System;
using Models;
using Models.Core;
using Models.Climate;
using Models.PMF;

/// <summary>Photoperiod flower induction gate for strawberry.</summary>
[Serializable]
public class Script : Model
{
    // -------------------------------------------------------
    // Links
    // -------------------------------------------------------
    [Link] private Plant Plant = null;
    [Link] private Clock Clock = null;
    [Link] private Weather Weather = null;
    // Phenology's Progression reads the gate from this Constant rather than
    // from [StrawberryPhotoperiod].PhotoperiodGate directly - cross-referencing
    // a Manager script's own properties by bracket-path is not reliably
    // resolvable at runtime in this APSIM build (confirmed empirically: it
    // fails identically whether read from a Report or a VariableReference).
    // Written via Node.Set() with an explicit path rather than [Link]: a
    // plain [Link] by type+name silently bound to the wrong Constant
    // (Phenology.BaseThermalTime's "TMin") when many Constant-typed nodes
    // exist in the same subtree, and [Link(Path=...)] did not fix this
    // either - confirmed empirically both times by seeing TMin's value
    // overwritten from 5.0 to the gate's 0/1 value, which was quietly
    // inflating thermal-time accumulation for every phase.

    // -------------------------------------------------------
    // Parameters
    // -------------------------------------------------------

    /// <summary>
    /// Cultivar type: 0 = Short-day (SD), 1 = Day-neutral (DN).
    /// Override in Cultivar node.
    /// </summary>
    [Description("Cultivar type: 0 = Short-day, 1 = Day-neutral")]
    public int CultivarType { get; set; } = 0;

    // -- SD parameters --

    /// <summary>
    /// Critical photoperiod for flower induction in SD cultivars (hours).
    /// Flowering occurs when daylength FALLS BELOW this threshold.
    /// Typical range: 12–14 h; default 14 h.
    /// </summary>
    [Description("Critical daylength for SD flower induction (h)")]
    public double CriticalDayLength { get; set; } = 14.0;

    /// <summary>Minimum mean temperature for flower induction (°C).</summary>
    [Description("Minimum mean temperature for SD flower induction (°C)")]
    public double MinInductiveTemp { get; set; } = 8.0;

    /// <summary>Maximum mean temperature for flower induction (°C).</summary>
    [Description("Maximum mean temperature for SD flower induction (°C)")]
    public double MaxInductiveTemp { get; set; } = 25.0;

    /// <summary>
    /// Minimum number of consecutive short days required
    /// before the induction gate opens.
    /// Typical: 7–14 days.
    /// </summary>
    [Description("Minimum consecutive inductive days required")]
    public int MinInductiveDays { get; set; } = 10;

    // -- DN parameters --

    /// <summary>
    /// Mean temperature above which flowering is suppressed in
    /// DN cultivars (°C). Typical: 26–28 °C.
    /// </summary>
    [Description("Heat suppression threshold for DN cultivars (°C)")]
    public double HeatSuppressionThreshold { get; set; } = 26.0;

    // -------------------------------------------------------
    // Outputs
    // -------------------------------------------------------

    /// <summary>
    /// 1 = flowering can proceed; 0 = blocked.
    /// Used as a multiplier on Phenology Progression.
    /// </summary>
    [Description("Photoperiod/temperature gate for flower induction (0 or 1)")]
    public double PhotoperiodGate { get; private set; } = 0.0;

    /// <summary>Count of consecutive inductive short days (SD only).</summary>
    [Description("Consecutive inductive days accumulated (SD only)")]
    public int InductiveDaysAccumulated { get; private set; } = 0;

    /// <summary>Today's calculated daylength (hours).</summary>
    [Description("Calculated daylength (h)")]
    public double Daylength { get; private set; } = 12.0;

    // -------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------

    // Replacements enforces one shared copy of this script (and its
    // CultivarType default) across every simulation that reuses this Plant
    // definition, so a per-simulation override of the CultivarType parameter
    // doesn't stick. Cultivar-specific switching is done here instead, via
    // the name the crop was actually sown with (Plant.CultivarName), which
    // *is* simulation-specific at runtime.
    private int GetEffectiveCultivarType()
    {
        if (Plant.SowingData != null && Plant.SowingData.Cultivar == "GenericSD")
            return 0; // short-day (e.g. Australian production cultivars)
        return CultivarType; // Albion/SanAndreas/unspecified -> configured default (DN)
    }

    [EventSubscribe("StartOfDay")]
    private void OnStartOfDay(object sender, EventArgs e)
    {
        Daylength = CalcDaylength(Weather.Latitude, Clock.Today.DayOfYear);
        double tmean = (Weather.MaxT + Weather.MinT) / 2.0;

        if (GetEffectiveCultivarType() == 1)
        {
            // DN cultivar: gate = 1 unless heat suppression
            PhotoperiodGate = (tmean < HeatSuppressionThreshold) ? 1.0 : 0.0;
            InductiveDaysAccumulated = 0; // not applicable
        }
        else
        {
            // SD cultivar
            bool inductivePhotoperiod = Daylength < CriticalDayLength;
            bool inductiveTemperature = tmean >= MinInductiveTemp
                                     && tmean <= MaxInductiveTemp;

            if (inductivePhotoperiod && inductiveTemperature)
                InductiveDaysAccumulated++;
            else
                InductiveDaysAccumulated = 0; // reset on non-inductive day

            bool gateOpen = InductiveDaysAccumulated >= MinInductiveDays;
            PhotoperiodGate = gateOpen ? 1.0 : 0.0;
        }

        Node.Set("[Phenology].PhotoperiodGateValue.FixedValue", PhotoperiodGate, this);
    }

    // -------------------------------------------------------
    // Astronomical daylength calculation
    // Spencer (1971) / Forsythe et al. (1995) approximation
    // latitude: degrees (positive = N, negative = S)
    // doy: day of year (1–365)
    // Returns: daylength in decimal hours
    // -------------------------------------------------------
    private static double CalcDaylength(double latitude, int doy)
    {
        double latRad = latitude * Math.PI / 180.0;
        double declination = 0.006918
            - 0.399912 * Math.Cos(2 * Math.PI * doy / 365.0)
            + 0.070257 * Math.Sin(2 * Math.PI * doy / 365.0)
            - 0.006758 * Math.Cos(4 * Math.PI * doy / 365.0)
            + 0.000907 * Math.Sin(4 * Math.PI * doy / 365.0);

        double cosHourAngle = -Math.Tan(latRad) * Math.Tan(declination);

        // Clamp to [-1, 1] for polar day/night edge cases
        cosHourAngle = Math.Max(-1.0, Math.Min(1.0, cosHourAngle));

        double hourAngle = Math.Acos(cosHourAngle);
        return 2.0 * hourAngle * 180.0 / Math.PI / 15.0; // convert to hours
    }
}
