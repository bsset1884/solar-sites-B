import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <div className="band">
      <div>
        <h1 className="band__title">Page not found</h1>
        <p className="muted">This page does not exist (any more).</p>
      </div>
      <Link to="/" className="btn btn--primary">
        To your sites
      </Link>
    </div>
  );
}
