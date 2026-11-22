import { Link } from "react-router";
import { api } from "../api";
import { ArrowRight } from "../components/Icons";
import { formatDecimal } from "../format";
import { useApi } from "../hooks";

export default function SitesPage() {
  const sites = useApi((signal) => api.listSites(signal), []);

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">
          Client sites
          <span className="page-title__soft">ready for the sun</span>
        </h1>
        <Link to="/sites/new" className="btn btn--primary">
          New site <ArrowRight />
        </Link>
      </div>

      {sites.error && (
        <p className="alert" role="alert">
          {sites.error}
        </p>
      )}
      {sites.loading && !sites.data && <p className="muted">Loading sites…</p>}

      {sites.data && sites.data.length === 0 && (
        <div className="band">
          <div>
            <h2 className="band__title">No sites yet</h2>
            <p className="muted">Add your first client to see what their roof can produce.</p>
          </div>
          <Link to="/sites/new" className="btn btn--primary">
            Add a site <ArrowRight />
          </Link>
        </div>
      )}

      {sites.data && sites.data.length > 0 && (
        <ul className="site-grid">
          {sites.data.map((site) => (
            <li key={site.id}>
              <Link to={`/sites/${site.id}`} className="card site-card">
                <span className="site-card__name">{site.clientName}</span>
                <span className="site-card__address">{site.address}</span>
                <span className="site-card__facts">
                  <span className="pill">{formatDecimal(site.peakKwp)} kWp</span>
                  {site.roofAreaM2 !== null && <span className="pill">{formatDecimal(site.roofAreaM2)} m² roof</span>}
                </span>
                <span className="site-card__open">
                  View estimate <ArrowRight />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
