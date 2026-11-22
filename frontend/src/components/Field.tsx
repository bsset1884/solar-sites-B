import type { InputHTMLAttributes, ReactNode } from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  name: string;
  label: string;
  error?: string;
  hint?: ReactNode;
};

/** A labelled input with its hint and its error message underneath. */
export default function Field({ name, label, error, hint, className, ...input }: FieldProps) {
  const id = `field-${name}`;
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ");
  return (
    <div className={`field ${className ?? ""}`}>
      <label htmlFor={id} className="field__label">
        {label}
      </label>
      <input
        id={id}
        name={name}
        className="field__input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        {...input}
      />
      {hint && (
        <p id={`${id}-hint`} className="field__hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}
