import { useState, type CSSProperties } from "react";
import { MONTH_NAMES, formatKwh, formatNumber } from "../format";

type Month = { month: number; kwh: number };

/** Gridlines on round numbers (0, 200, 400, ...): about four steps up to the maximum. */
export function niceScale(max: number): { top: number; ticks: number[] } {
  if (!(max > 0)) return { top: 1, ticks: [0] };
  const roughStep = max / 4;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const step = [1, 2, 5, 10].map((factor) => factor * magnitude).find((candidate) => candidate >= roughStep)!;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let tick = 0; tick <= top; tick += step) ticks.push(tick);
  return { top, ticks };
}

/** Column chart of the 12 months, with a hover/focus tooltip and a table view. */
export default function MonthlyChart({ months }: { months: Month[] }) {
  const [showTable, setShowTable] = useState(false);
  const { top, ticks } = niceScale(Math.max(...months.map((m) => m.kwh)));
  const peak = months.reduce((best, m) => (m.kwh > best.kwh ? m : best), months[0]);

  return (
    <figure className="chart">
      <div className="chart__head">
        <figcaption className="chart__title">Production per month</figcaption>
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
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col" className="num">
                Production
              </th>
            </tr>
          </thead>
          <tbody>
            {months.map((m) => (
              <tr key={m.month}>
                <th scope="row">{MONTH_NAMES[m.month - 1]}</th>
                <td className="num">{formatKwh(m.kwh)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="columns">
          <div className="columns__plot">
            <div className="columns__grid" aria-hidden="true">
              {ticks.map((tick) => (
                <div key={tick} className="columns__gridline" style={{ bottom: `${(tick / top) * 100}%` }}>
                  <span>{formatNumber(tick)}</span>
                </div>
              ))}
            </div>
            <ol className="columns__bars" aria-label="Production per month in kWh">
              {months.map((m) => (
                <li
                  key={m.month}
                  className="columns__col"
                  tabIndex={0}
                  style={{ "--bar-height": `${(m.kwh / top) * 100}%` } as CSSProperties}
                >
                  <span className="columns__bar" />
                  {m === peak && (
                    <span className="columns__cap" aria-hidden="true">
                      {formatNumber(m.kwh)}
                    </span>
                  )}
                  <span className="tooltip columns__tip">
                    <strong>{formatKwh(m.kwh)}</strong>
                    <span>{MONTH_NAMES[m.month - 1]}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div className="columns__labels" aria-hidden="true">
            {months.map((m) => (
              <span key={m.month}>
                <span className="columns__label-long">{MONTH_NAMES[m.month - 1].slice(0, 3)}</span>
                <span className="columns__label-short">{MONTH_NAMES[m.month - 1][0]}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </figure>
  );
}
