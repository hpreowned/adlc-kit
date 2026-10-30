using Kestrel.Pricing.Common;
using Kestrel.Pricing.Tests.Support;

namespace Kestrel.Pricing.Tests;

/// <summary>ADLC harness overlay for svc-009: the fuel surcharge rounds half away from zero.</summary>
public class AdlcOverlayRoundingTests
{
    [Theory]
    [InlineData("33.00", "4.13")] // 4.125 -> away from zero
    [InlineData("33.16", "4.15")] // 4.145 -> away from zero
    [InlineData("33.08", "4.14")] // 4.135 -> same under both modes
    public void ApplyFuelSurcharge_RoundsMidpointsAwayFromZero(string baseAmount, string expected)
    {
        var calculator = TestDefaults.Calculator(fuelPct: 12.5m);

        var surcharge = calculator.ApplyFuelSurcharge(decimal.Parse(baseAmount));

        Assert.Equal(decimal.Parse(expected), surcharge);
    }

    [Theory]
    [InlineData("33.00")]
    [InlineData("33.16")]
    [InlineData("24.00")]
    public void ApplyFuelSurcharge_AlwaysEqualsMoneyRound(string baseAmount)
    {
        var calculator = TestDefaults.Calculator(fuelPct: 12.5m);
        var amount = decimal.Parse(baseAmount);

        Assert.Equal(Money.Round(amount * 12.5m / 100m), calculator.ApplyFuelSurcharge(amount));
    }

    [Fact]
    public void Calculate_FuelLineAndTotalUseAwayFromZero()
    {
        // NSL domestic 0-50 kg band: 18.00 base + 0.60/kg, 25 kg -> 33.00 linehaul, fuel 4.125.
        var calculator = TestDefaults.Calculator(fuelPct: 12.5m);

        var quote = calculator.Calculate("NSL", "NLRTM", "NLAMS", Geo.Zone.Domestic, 25m);

        Assert.NotNull(quote);
        Assert.Equal(4.13m, quote!.Lines.Single(l => l.Code == "FUEL").Amount);
        Assert.Equal(37.13m, quote.Amount);
    }
}
