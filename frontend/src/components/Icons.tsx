// Small inline SVG icons; aria-hidden because the text next to them says it all.

export function SunMark() {
  return (
    <svg className="sun-mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="6.5" />
      <path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M6.8 25.2l2.8-2.8M22.4 9.6l2.8-2.8" />
    </svg>
  );
}

export function ArrowRight() {
  return (
    <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

export function ArrowLeft() {
  return (
    <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M13 8H3M7 4 3 8l4 4" />
    </svg>
  );
}

export function ExternalArrow() {
  return (
    <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M5 11 11 5M6 5h5v5" />
    </svg>
  );
}
