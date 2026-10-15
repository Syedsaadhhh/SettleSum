import { X } from "lucide-react";
import { useEffect, useRef } from "react";
export default function Drawer({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.querySelector("button,input,select,textarea")?.focus();
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const elements = Array.from(
          ref.current.querySelectorAll(
            "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
          ),
        );
        const first = elements[0],
          last = elements[elements.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="drawer-layer">
      <div className="drawer-scrim" onClick={onClose} />
      <section
        className={`drawer ${wide ? "wide-drawer" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        ref={ref}
      >
        <div className="drawer-heading">
          <div>
            <h2 id="drawer-title">{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button
            className="icon-button"
            aria-label="Close drawer"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
