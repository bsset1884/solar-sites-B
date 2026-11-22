import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, errorMessage } from "../api";
import BatteryPanel from "../components/BatteryPanel";
import { ArrowLeft, ExternalArrow } from "../components/Icons";
import MonthlyChart from "../components/MonthlyChart";
import { formatDecimal, formatNumber } from "../format";
import { useApi } from "../hooks";

export default function SiteDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const site = useApi((signal) => api.getSite(id, signal), [id]);
  const production = useApi((signal) => api.production(id, signal), [id]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteSite(id);
      navigate("/", { replace: true });
    } catch (error) {
      setDeleteError(errorMessage(error));
      setDeleting(false);
    }
  }

  if (site.error) {
    return (
      <>
        <Link to="/" className="back-link">
          <ArrowLeft /> All sites
        </Link>
        <p className="alert" role="alert">
          {site.error}
        </p>
      </>
    );
  }
  if (!site.data) return <p className="muted">Loading site…</p>;

  const { clientName, address, latitude, longitude, roofAreaM2, peakKwp } = site.data;
  const mapLink = `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=18/${latitude}/${longitude}`;

  return (
    <>
      <Link to="/" className="back-link">
        <ArrowLeft /> All sites
      </Link>

      <div className="page-head">
        <div>
          <h1 className="page-title">{clientName}</h1>
          <p className="muted">{address}</p>
          <p className="site-facts">
            <span className="pill">{formatDecimal(peakKwp)} kWp panels</span>
            {roofAreaM2 !== null && <span className="pill">{formatDecimal(roofAreaM2)} m² roof</span>}
            <a className="pill pill--link" href={mapLink} target="_blank" rel="noopener noreferrer">
              {latitude}, {longitude} <ExternalArrow />
            </a>
          </p>
        </div>
        <div className="page-head__actions">
          <Link to={`/sites/${id}/edit`} className="btn btn--outline">
            Edit
          </Link>
          <button type="button" className="btn btn--ghost btn--danger" onClick={() => setConfirmDelete(true)}>
            Delete
          </button>
        </div>
      </div>

      {confirmDelete && (
        <div className="band band--danger" role="alertdialog" aria-labelledby="delete-title">
          <div>
            <h2 id="delete-title" className="band__title">
              Delete {clientName}?
            </h2>
            <p className="muted">This removes the site for good.</p>
            {deleteError && <p className="field__error">{deleteError}</p>}
          </div>
          <div className="band__actions">
            <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
            <button type="button" className="btn btn--danger-solid" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete site"}
            </button>
          </div>
        </div>
      )}

      <section className="card section" aria-labelledby="production-title">
        <div className="section__head">
          <h2 id="production-title">Solar production</h2>
          <p className="muted">An average year, with the panels at the best angle for this location.</p>
        </div>
        {production.error && (
          <>
            <p className="alert" role="alert">
              {production.error}
            </p>
            <p className="muted">
              Is the location right? <Link to={`/sites/${id}/edit`}>Check the coordinates</Link>.
            </p>
          </>
        )}
        {production.loading && !production.data && <p className="muted">Asking PVGIS…</p>}
        {production.data && (
          <>
            <p className="hero-figure">
              {formatNumber(production.data.yearlyKwh)} <span className="hero-figure__unit">kWh per year</span>
            </p>
            <MonthlyChart months={production.data.monthlyKwh} />
            <p className="footnote">
              Source: PVGIS 5.3 by the European Commission (long-term average), with 14% system losses.
            </p>
          </>
        )}
      </section>

      {!production.error && <BatteryPanel siteId={id} />}
    </>
  );
}
