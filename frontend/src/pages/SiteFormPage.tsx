import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, api, errorMessage, type Site, type SitePayload } from "../api";
import Field from "../components/Field";
import { ArrowLeft, ExternalArrow } from "../components/Icons";
import { parseDecimal } from "../format";
import { useApi } from "../hooks";

type FieldName = "clientName" | "address" | "latitude" | "longitude" | "roofAreaM2" | "peakKwp";
type Values = Record<FieldName, string>;

const EMPTY: Values = { clientName: "", address: "", latitude: "", longitude: "", roofAreaM2: "", peakKwp: "" };
const NUMBER_FIELDS = ["latitude", "longitude", "roofAreaM2", "peakKwp"] as const;

function toValues(site: Site): Values {
  return {
    clientName: site.clientName,
    address: site.address,
    latitude: String(site.latitude),
    longitude: String(site.longitude),
    roofAreaM2: site.roofAreaM2 === null ? "" : String(site.roofAreaM2),
    peakKwp: String(site.peakKwp),
  };
}

/** The JSON body. The server checks everything and answers with a message per
 * field, so the rules live in one place (the backend). */
function toPayload(values: Values): SitePayload {
  const payload: SitePayload = { clientName: values.clientName, address: values.address };
  for (const field of NUMBER_FIELDS) {
    const text = values[field].trim();
    if (text === "") {
      if (field === "roofAreaM2") payload[field] = null; // optional
      continue; // a missing required number gets "This field is required."
    }
    payload[field] = parseDecimal(text) ?? text; // not a number: the server says so
  }
  return payload;
}

export default function SiteFormPage() {
  const { id } = useParams();
  const editing = id !== undefined;
  const navigate = useNavigate();
  const existing = useApi((signal) => (id ? api.getSite(id, signal) : Promise.resolve(null)), [id]);

  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (existing.data) setValues(toValues(existing.data));
  }, [existing.data]);

  const change = (field: FieldName) => (event: ChangeEvent<HTMLInputElement>) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setErrors({});
    setFormError(null);
    try {
      const payload = toPayload(values);
      const site = id ? await api.updateSite(id, payload) : await api.createSite(payload);
      navigate(`/sites/${site.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setErrors(error.fieldErrors);
        setFormError("Please check the highlighted fields.");
      } else {
        setFormError(errorMessage(error));
      }
    } finally {
      setSaving(false);
    }
  }

  const backTo = id ? `/sites/${id}` : "/";
  if (editing && existing.error) {
    return (
      <>
        <Link to="/" className="back-link">
          <ArrowLeft /> All sites
        </Link>
        <p className="alert" role="alert">
          {existing.error}
        </p>
      </>
    );
  }

  const mapSearch = `https://www.openstreetmap.org/search?query=${encodeURIComponent(values.address)}`;

  return (
    <>
      <Link to={backTo} className="back-link">
        <ArrowLeft /> {id ? "Back to site" : "All sites"}
      </Link>
      <h1 className="page-title">{editing ? "Edit site" : "New site"}</h1>

      <form className="card form-card" onSubmit={handleSubmit} noValidate aria-busy={editing && existing.loading}>
        {formError && (
          <p className="alert" role="alert">
            {formError}
          </p>
        )}
        <div className="form-grid">
          <Field
            name="clientName"
            label="Client name"
            className="form-grid__wide"
            autoComplete="off"
            value={values.clientName}
            onChange={change("clientName")}
            error={errors.clientName}
          />
          <Field
            name="address"
            label="Address"
            className="form-grid__wide"
            autoComplete="off"
            value={values.address}
            onChange={change("address")}
            error={errors.address}
            hint={
              values.address.trim() ? (
                <a href={mapSearch} target="_blank" rel="noopener noreferrer">
                  Find the coordinates on OpenStreetMap <ExternalArrow />
                </a>
              ) : (
                "Street, number and town."
              )
            }
          />
          <Field
            name="latitude"
            label="Latitude"
            inputMode="decimal"
            placeholder="52.0799"
            value={values.latitude}
            onChange={change("latitude")}
            error={errors.latitude}
            hint="Decimal degrees, −90 to 90."
          />
          <Field
            name="longitude"
            label="Longitude"
            inputMode="decimal"
            placeholder="4.3113"
            value={values.longitude}
            onChange={change("longitude")}
            error={errors.longitude}
            hint="Decimal degrees, −180 to 180."
          />
          <Field
            name="roofAreaM2"
            label="Roof area (m²) · optional"
            inputMode="decimal"
            value={values.roofAreaM2}
            onChange={change("roofAreaM2")}
            error={errors.roofAreaM2}
          />
          <Field
            name="peakKwp"
            label="Panel capacity (kWp)"
            inputMode="decimal"
            placeholder="5"
            value={values.peakKwp}
            onChange={change("peakKwp")}
            error={errors.peakKwp}
            hint="Total peak power of all panels."
          />
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={saving}>
            {saving ? "Saving…" : editing ? "Save changes" : "Save site"}
          </button>
          <Link to={backTo} className="btn btn--ghost">
            Cancel
          </Link>
        </div>
      </form>
    </>
  );
}
