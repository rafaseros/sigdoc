// SigDoc primitives — buttons, inputs, badges, dialog, search

const Button = ({ variant = "outline", size, icon, children, className = "", ...props }) => {
  const cls = ["btn", `btn-${variant}`, size && `btn-${size}`, className].filter(Boolean).join(" ");
  return (
    <button className={cls} {...props}>
      {icon}
      {children}
    </button>
  );
};

const IconButton = ({ icon, variant = "ghost", size = "sm", title, ...props }) => (
  <Button variant={variant} size={size} className="btn-icon" title={title} {...props}>{icon}</Button>
);

const Pill = ({ variant = "secondary", children, style, dot, ...props }) => {
  const cls = ["pill", `pill-${variant}`, dot && "pill-dot"].filter(Boolean).join(" ");
  return <span className={cls} style={style} {...props}>{children}</span>;
};

const Input = ({ ...props }) => <input className="input" {...props} />;
const Textarea = ({ ...props }) => <textarea className="input textarea" {...props} />;
const Select = ({ children, ...props }) => (
  <select className="input" {...props}>{children}</select>
);

const Field = ({ label, htmlFor, children, hint, style }) => (
  <div className="field" style={style}>
    {label && <label className="label" htmlFor={htmlFor}>{label}</label>}
    {children}
    {hint && <div className="tiny">{hint}</div>}
  </div>
);

const Search = ({ value, onChange, placeholder, style }) => (
  <div className="search" style={style}>
    <SearchIcon size={15}/>
    <input className="input" value={value} onChange={onChange} placeholder={placeholder}/>
  </div>
);

const Avatar = ({ name, size = "" }) => {
  const initials = (name || "?").split(/[\s.@]+/).filter(Boolean).slice(0,2).map(s=>s[0]?.toUpperCase()).join("");
  const cls = ["avatar", size && `avatar-${size}`].filter(Boolean).join(" ");
  return <span className={cls}>{initials}</span>;
};

const Banner = ({ variant = "info", icon, children }) => (
  <div className={`banner banner-${variant}`}>{icon}<div style={{flex:1}}>{children}</div></div>
);

const Dialog = ({ open, onClose, title, description, footer, width = 560, children }) => {
  if (!open) return null;
  return (
    <>
      <div className="dialog-overlay" onClick={onClose}/>
      <div className="dialog" style={{maxWidth: width}}>
        <div className="dialog-header">
          {title && <div className="dialog-title">{title}</div>}
          {description && <div className="dialog-desc">{description}</div>}
          <button className="btn btn-ghost btn-icon dialog-close" onClick={onClose} title="Cerrar">
            <XIcon size={16}/>
          </button>
        </div>
        <div className="dialog-body">{children}</div>
        {footer && <div className="dialog-footer">{footer}</div>}
      </div>
    </>
  );
};

const Toast = ({ show, children, variant = "ok" }) => {
  if (!show) return null;
  return (
    <div className="toast">
      {variant === "ok" ? <CheckCircleIcon size={16} style={{color:"#059669"}}/> : <AlertCircleIcon size={16} style={{color:"#ba1a1a"}}/>}
      {children}
    </div>
  );
};

const Tabs = ({ tabs, active, onChange, variant = "underline" }) => (
  <div className={variant === "pill" ? "row-gap" : "tabs"} style={variant === "pill" ? {gap:6, marginBottom:20} : undefined}>
    {tabs.map(t => (
      <span key={t.id} className={`${variant === "pill" ? "tab-pill" : "tab"} ${active === t.id ? "active" : ""}`} onClick={()=>onChange?.(t.id)}>
        {t.icon}
        {t.label}
        {t.count != null && <Pill variant={active === t.id ? "accent-soft" : "secondary"} style={{height:18, fontSize:10.5, padding:"0 7px"}}>{t.count}</Pill>}
      </span>
    ))}
  </div>
);

Object.assign(window, { Button, IconButton, Pill, Input, Textarea, Select, Field, Search, Avatar, Banner, Dialog, Toast, Tabs });
