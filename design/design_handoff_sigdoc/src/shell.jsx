// SigDoc app shell — top nav, user menu

const NAV_ITEMS = [
  { id: "templates", label: "Plantillas", icon: <FolderIcon size={15}/> },
  { id: "users",     label: "Usuarios",   icon: <UsersIcon size={15}/> },
  { id: "audit",     label: "Auditoría",  icon: <ShieldIcon size={15}/> },
];

const UserChip = ({ user, onLogout, onChangePass }) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  return (
    <div ref={ref} style={{position:"relative"}}>
      <button className="user-chip" onClick={()=>setOpen(o=>!o)}>
        <Avatar name={user.nombre}/>
        <span className="user-chip-text">
          <span className="user-chip-name">{user.nombre.split(" ").slice(0,2).join(" ")}</span>
          <span className="user-chip-role">{user.rol}</span>
        </span>
        <ChevronDownIcon size={14} style={{color:"#515f74", transform: open?"rotate(180deg)":"none", transition:"transform 150ms"}}/>
      </button>
      {open && (
        <div style={{position:"absolute", top:48, right:0, width:260, background:"#fff", borderRadius:12, padding:6, boxShadow:"0 12px 32px rgba(25,28,30,0.10), 0 0 0 1px rgba(195,198,215,0.30)", zIndex:40}}>
          <div style={{padding:"12px 12px 10px", borderBottom:"1px solid rgba(195,198,215,0.20)"}}>
            <div style={{fontSize:13.5, fontWeight:600}}>{user.nombre}</div>
            <div className="mono" style={{fontSize:11.5, color:"#515f74", marginTop:2}}>{user.email}</div>
            <Pill variant="accent-soft" style={{marginTop:8}}>{user.rol}</Pill>
          </div>
          <button className="btn btn-ghost" style={{width:"100%", justifyContent:"flex-start", marginTop:4}} onClick={onChangePass}>
            <KeyIcon size={14}/> Cambiar contraseña
          </button>
          <div style={{height:1, background:"rgba(195,198,215,0.20)", margin:"4px 0"}}/>
          <button className="btn btn-ghost" style={{width:"100%", justifyContent:"flex-start", color:"#ba1a1a"}} onClick={onLogout}>
            <LogOutIcon size={14}/> Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
};

const AppShell = ({ active, onNav, onLogout, onChangePass, currentUser, children, wide=false, breadcrumbs }) => (
  <div style={{minHeight:"100vh"}}>
    <header className="shell-header">
      <div className="shell-inner">
        <div style={{display:"flex", alignItems:"center", gap:32}}>
          <div className="wordmark" onClick={()=>onNav?.("templates")} style={{cursor:"pointer"}}>
            <span className="wordmark-dot">S</span>
            SigDoc
          </div>
          <nav className="nav">
            {NAV_ITEMS.map(item => (
              <span key={item.id} className={`nav-link ${active === item.id ? "active" : ""}`} onClick={()=>onNav?.(item.id)}>
                {item.icon}{item.label}
              </span>
            ))}
          </nav>
        </div>
        <div style={{display:"flex", alignItems:"center", gap:12}}>
          <UserChip user={currentUser} onLogout={onLogout} onChangePass={onChangePass}/>
        </div>
      </div>
    </header>
    {breadcrumbs && (
      <div style={{maxWidth: wide ? 1440 : 1280, margin:"0 auto", padding:"14px 24px 0"}}>
        {breadcrumbs}
      </div>
    )}
    <main className={`shell-main ${wide ? "shell-main-wide" : ""}`}>{children}</main>
  </div>
);

const Breadcrumbs = ({ items }) => (
  <div style={{display:"flex", alignItems:"center", gap:6, fontSize:12.5, color:"#515f74"}}>
    {items.map((it, i) => (
      <React.Fragment key={i}>
        {i > 0 && <ChevronRightIcon size={12} style={{color:"#a0a4af"}}/>}
        {it.onClick ? (
          <span style={{cursor:"pointer", color: i === items.length - 1 ? "#191c1e" : "#515f74", fontWeight: i === items.length - 1 ? 600 : 500}} onClick={it.onClick}>{it.label}</span>
        ) : (
          <span style={{color: i === items.length - 1 ? "#191c1e" : "#515f74", fontWeight: i === items.length - 1 ? 600 : 500}}>{it.label}</span>
        )}
      </React.Fragment>
    ))}
  </div>
);

Object.assign(window, { AppShell, UserChip, Breadcrumbs, NAV_ITEMS });
