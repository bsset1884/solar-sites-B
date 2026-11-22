import { useState } from "react";
import { api, type BatteryResult, type Scenario } from "../api";
import { formatDecimal, formatKwh, formatPercent, parseDecimal } from "../format";
import { useApi, useDebounced } from "../hooks";

// Average yearly electricity use of Dutch households by size (see README).
const HOUSEHOLDS = [
  { label: "1 person", kwh: 1600 },
  { label: "2 people", kwh: 2500 },
  { label: "3 people", kwh: 3400 },
  { label: "4 people", kwh: 4300 },
  { label: "5 people", kwh: 5000 },
];

export default function BatteryPanel({ siteId }: { siteId: string }) {
  const [useText, setUseText] = useState("2500");
  const [capacity, setCapacity] = useState(5);

  const annualUse = parseDecimal(useText);
  const useIsValid = annualUse !== null && annualUse > 0 && annualUse <= 1_000_000;
  // Wait until the advisor stops typing or sliding before asking the server.
  const queryUse = useDebounced(useIsValid ? annualUse : null, 400);
  const queryCapacity = useDebounced(capacity, 250);

  const battery = useApi(
    (signal) =>
      queryUse === null
        ? Promise.resolve(null)
        : api
            .battery(siteId, queryCapacity, queryUse, signal)
            .then((result) => ({ result, capacity: queryCapacity })),
    [siteId, queryCapacity, queryUse],
  );

  return (
    <section className="card section" aria-labelledby="battery-title">
      <div className="section__head">
        <h2 id="battery-title">Home battery</h2>
        <p className="muted">How much of the solar energy would the client use themselves, with and without a battery?</p>
      </div>

      <div className="battery-inputs">
        <div className="field">
          <label htmlFor="annual-use" className="field__label">
            Yearly electricity use of the household
          </label>
          <div className="input-with-unit">
            <input
              id="annual-use"
              className="field__input"
              inputMode="numeric"
              value={useText}
              onChange={(event) => setUseText(event.target.value)}
              aria-invalid={useIsValid ? undefined : true}
              aria-describedby="annual-use-hint"
            />
            <span className="input-with-unit__unit">kWh</span>
          </div>
          <p id="annual-use-hint" className={useIsValid ? "field__hint" : "field__error"}>
            {useIsValid
              ? "From the client's energy bill, or pick a typical household:"
              : "Enter a number above 0 (in kWh per year)."}
          </p>
          <div className="chips" role="group" aria-label="Typical households">
            {HOUSEHOLDS.map((household) => (
              <button
                key={household.kwh}
                type="button"
                className="chip"
                aria-pressed={annualUse === household.kwh}
                onClick={() => setUseText(String(household.kwh))}
              >
                {household.label} · {household.kwh.toLocaleString("en-GB")}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="capacity" className="field__label">
            Battery capacity <output htmlFor="capacity">{formatDecimal(capacity)} kWh</output>
          </label>
          <input
            id="capacity"
            type="range"
            min={0}
            max={20}
            step={0.5}
            value={capacity}
            onChange={(event) => setCapacity(Number(event.target.value))}
            className="range"
          />
          <div className="range__scale" aria-hidden="true">
            <span>0</span>
            <span>5</span>
            <span>10</span>
            <span>15</span>
            <span>20</span>
          </div>
        </div>
      </div>

      {battery.error && (
        <p className="alert" role="alert">
          {battery.error}
        </p>
      )}
      {!battery.data && battery.loading && <p className="muted">Calculating hour by hour…</p>}
      {battery.data && (
        <div className={battery.loading ? "is-refreshing" : undefined} aria-busy={battery.loading}>
          <BatteryResults result={battery.data.result} capacity={battery.data.capacity} />
        </div>
      )}
    </section>
  );
}

function BatteryResults({ result, capacity }: { result: BatteryResult; capacity: number }) {
  const [showTable, setShowTable] = useState(false);
  const without = result.withoutBattery;
  const withBattery = result.withBattery;
  const added = withBattery.selfUsedKwh - without.selfUsedKwh;
  const batteryName = `With a ${formatDecimal(capacity)} kWh battery`;

  return (
    <>
      <div className="stats">
        <div className="stat">
          <p className="stat__label">Solar energy used at home</p>
          <p className="stat__value">{formatKwh(withBattery.selfUsedKwh)}</p>
          <p className="stat__note">without a battery: {formatKwh(without.selfUsedKwh)}</p>
        </div>
        <div className="stat stat--accent">
          <p className="stat__label">What the battery adds</p>
          <p className="stat__value">+{formatKwh(added)}</p>
          <p className="stat__note">
            per year · self-consumption {formatPercent(without.selfConsumptionPct)} →{" "}
            {formatPercent(withBattery.selfConsumptionPct)}
          </p>
        </div>
        <div className="stat">
          <p className="stat__label">Household use covered by solar</p>
          <p className="stat__value">{formatPercent(withBattery.selfSufficiencyPct)}</p>
          <p className="stat__note">without a battery: {formatPercent(without.selfSufficiencyPct)}</p>
        </div>
      </div>

      <figure className="chart">
        <div className="chart__head">
          <figcaption className="chart__title">
            Where the {formatKwh(result.productionKwh)} of solar energy goes
          </figcaption>
          <button
            type="button"
            className="btn btn--ghost btn--small"
            onClick={() => setShowTable(!showTable)}
            aria-pressed={showTable}
          >
            {showTable ? "Show chart" : "Show table"}
          </button>
        </div>
        {showTable ? (
          <ScenarioTable result={result} batteryName={batteryName} />
        ) : (
          <>
            <SplitBar title="Without a battery" scenario={without} production={result.productionKwh} />
            <SplitBar title={batteryName} scenario={withBattery} production={result.productionKwh} />
            <ul className="legend">
              <li>
                <span className="swatch swatch--home" /> Used at home
              </li>
              <li>
                <span className="swatch swatch--grid" /> Sent to the grid
              </li>
              {batteryLoss(result) >= 1 && (
                <li>
                  <span className="swatch swatch--loss" /> Lost in the battery ({formatKwh(batteryLoss(result))})
                </li>
              )}
            </ul>
          </>
        )}
      </figure>

      <p className="footnote">
        Household use follows a typical daily and seasonal pattern; the battery stores up to {formatDecimal(capacity)}{" "}
        kWh with 90% round-trip efficiency. Simulated hour by hour with real 2023 weather from PVGIS.
      </p>
    </>
  );
}

/** Charging and discharging cost energy: production that is neither used nor exported. */
function batteryLoss(result: BatteryResult): number {
  const { selfUsedKwh, gridExportKwh } = result.withBattery;
  return Math.max(0, result.productionKwh - selfUsedKwh - gridExportKwh);
}

/** One whole (the yearly production) split into its parts. Widths are shares of
 * the production, so energy lost in the battery shows as the empty end of the track. */
function SplitBar({ title, scenario, production }: { title: string; scenario: Scenario; production: number }) {
  const parts = [
    { name: "Used at home", kwh: scenario.selfUsedKwh, tone: "home" },
    { name: "Sent to the grid", kwh: scenario.gridExportKwh, tone: "grid" },
    { name: "Lost in the battery", kwh: production - scenario.selfUsedKwh - scenario.gridExportKwh, tone: "loss" },
  ];
  return (
    <div className="split">
      <p className="split__title">{title}</p>
      <div className="split__bar">
        {parts
          .filter((part) => part.kwh >= 1) // skips rounding leftovers of a few tenths

          .map((part) => {
            const share = production > 0 ? (part.kwh / production) * 100 : 0;
            return (
              <span
                key={part.tone}
                className={`split__part split__part--${part.tone}`}
                style={{ width: `${share}%` }}
                tabIndex={0}
              >
                {share >= 12 && <span aria-hidden="true">{Math.round(share)}%</span>}
                <span className="tooltip split__tip">
                  <strong>{formatKwh(part.kwh)}</strong>
                  <span>
                    {part.name} · {formatPercent(share)}
                  </span>
                </span>
              </span>
            );
          })}
      </div>
    </div>
  );
}

function ScenarioTable({ result, batteryName }: { result: BatteryResult; batteryName: string }) {
  const rows: [string, (s: Scenario) => string][] = [
    ["Used at home", (s) => formatKwh(s.selfUsedKwh)],
    ["Sent to the grid", (s) => formatKwh(s.gridExportKwh)],
    ["Lost in the battery", (s) => formatKwh(Math.max(0, result.productionKwh - s.selfUsedKwh - s.gridExportKwh))],
    ["Bought from the grid", (s) => formatKwh(s.gridImportKwh)],
    ["Self-consumption (share of production used at home)", (s) => formatPercent(s.selfConsumptionPct)],
    ["Self-sufficiency (share of use covered by solar)", (s) => formatPercent(s.selfSufficiencyPct)],
  ];
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th scope="col">Per year</th>
          <th scope="col" className="num">
            Without a battery
          </th>
          <th scope="col" className="num">
            {batteryName}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td className="num">{value(result.withoutBattery)}</td>
            <td className="num">{value(result.withBattery)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
