// SigDoc — User management dialogs (Crear, Editar, Baja)
// Three full-fidelity flows for the Users admin screen.

const ROLE_OPTIONS = [
  {
    value: "Admin",
    label: "Administrador",
    desc: "Acceso total. Puede crear, editar y dar de baja usuarios, gestionar plantillas y ver auditoría.",
    icon: "Shield",
  },
  {
    value: "Creador",
    label: "Creador de plantillas",
    desc: "Sube y edita plantillas .docx, comparte con el equipo y genera documentos.",
    icon: "Edit",
  },
  {
    value: "Generador",
    label: "Generador",
    desc: "Solo puede generar documentos a partir de plantillas compartidas con su cuenta.",
    icon: "Sparkles",
  },
];

const RoleIcon = ({ name, size = 14 }) => {
  if (name === "Shield")   return <ShieldIcon size={size}/>;
  if (name === "Edit")     return <EditIcon size={size}/>;
  if (name === "Sparkles") return <SparklesIcon size={size}/>;
  return null;
};

// Reusable role picker — radio-card grid
const RolePicker = ({ value, onChange }) => (
  <div className="role-picker">
    {ROLE_OPTIONS.map(r => {
      const active = value === r.value;
      return (
        <label key={r.value} className={`role-card ${active ? "active" : ""}`}>
          <input
            type="radio"
            name="rol"
            value={r.value}
            checked={active}
            onChange={() => onChange(r.value)}
            style={{position:"absolute", opacity:0, pointerEvents:"none"}}
          />
          <div className="role-card-head">
            <span className="role-card-icon"><RoleIcon name={r.icon} size={14}/></span>
            <span className="role-card-title">{r.label}</span>
            <span className={`role-card-radio ${active ? "checked" : ""}`}>
              {active && <CheckIcon size={11}/>}
            </span>
          </div>
          <div className="role-card-desc">{r.desc}</div>
        </label>
      );
    })}
  </div>
);

// ─────────────────────────────────────────────────────────────
// 1. CREAR USUARIO
// ─────────────────────────────────────────────────────────────
const CreateUserDialog = ({ open, onClose, onCreated }) => {
  const [nombre, setNombre]   = React.useState("");
  const [email,  setEmail]    = React.useState("");
  const [rol,    setRol]      = React.useState("Generador");
  const [sendInvite, setSendInvite] = React.useState(true);
  const [tempPass, setTempPass]     = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setNombre(""); setEmail(""); setRol("Generador");
      setSendInvite(true); setTempPass(false); setSubmitting(false);
    }
  }, [open]);

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const canSubmit = nombre.trim().length >= 3 && validEmail && !submitting;

  const submit = () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setTimeout(() => {
      onCreated?.({ nombre, email, rol });
      onClose?.();
    }, 600);
  };

  const Footer = (
    <>
      <Button variant="outline" onClick={onClose}>Cancelar</Button>
      <Button
        variant="grad"
        icon={submitting ? <LoaderIcon size={13} className="spin"/> : <UserPlusIcon size={13}/>}
        onClick={submit}
        disabled={!canSubmit}
      >
        {submitting ? "Creando…" : "Crear usuario"}
      </Button>
    </>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Crear nuevo usuario"
      description="Se enviará un correo de invitación con instrucciones para establecer la contraseña inicial."
      footer={Footer}
      width={620}
    >
      <div style={{display:"flex", flexDirection:"column", gap:16}}>
        <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
          <Field label="Nombre completo" hint="Como debe aparecer en documentos y auditoría.">
            <Input
              placeholder="Ej. María López Vargas"
              value={nombre}
              onChange={e=>setNombre(e.target.value)}
              autoFocus
            />
          </Field>
          <Field
            label="Correo corporativo"
            hint={email && !validEmail ? <span style={{color:"#ba1a1a"}}>Formato de correo inválido.</span> : "Será el identificador único de la cuenta."}
          >
            <Input
              type="email"
              placeholder="usuario@cainco.org.bo"
              value={email}
              onChange={e=>setEmail(e.target.value)}
              style={email && !validEmail ? {borderColor:"#ba1a1a"} : undefined}
            />
          </Field>
        </div>

        <Field label="Rol del usuario">
          <RolePicker value={rol} onChange={setRol}/>
        </Field>

        <div className="settings-block">
          <div className="eyebrow" style={{marginBottom:10}}>Acceso inicial</div>
          <label className="check-row">
            <input type="checkbox" checked={sendInvite} onChange={e=>setSendInvite(e.target.checked)}/>
            <div>
              <div style={{fontSize:13, fontWeight:500}}>Enviar invitación por correo</div>
              <div className="tiny">El usuario recibirá un enlace para establecer su contraseña (válido 48 h).</div>
            </div>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={tempPass} onChange={e=>setTempPass(e.target.checked)}/>
            <div>
              <div style={{fontSize:13, fontWeight:500}}>Generar contraseña temporal</div>
              <div className="tiny">Se mostrará una sola vez. Se forzará el cambio en el primer inicio de sesión.</div>
            </div>
          </label>
        </div>

        <Banner variant="info" icon={<InfoIcon size={16} style={{color:"#004ac6"}}/>}>
          Esta acción quedará registrada en la <strong>Auditoría</strong> como <span className="mono" style={{fontSize:12}}>user_create</span>.
        </Banner>
      </div>
    </Dialog>
  );
};

// ─────────────────────────────────────────────────────────────
// 2. EDITAR USUARIO
// ─────────────────────────────────────────────────────────────
const EditUserDialog = ({ open, onClose, user, onSaved }) => {
  const [nombre, setNombre] = React.useState("");
  const [rol,    setRol]    = React.useState("Generador");
  const [estado, setEstado] = React.useState("Activo");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open && user) {
      setNombre(user.nombre);
      setRol(user.rol);
      setEstado(user.estado);
      setSubmitting(false);
    }
  }, [open, user]);

  if (!user) return null;

  const changed =
    nombre !== user.nombre || rol !== user.rol || estado !== user.estado;
  const diff = [];
  if (nombre !== user.nombre) diff.push({ k:"Nombre", from:user.nombre, to:nombre });
  if (rol    !== user.rol)    diff.push({ k:"Rol",    from:user.rol,    to:rol });
  if (estado !== user.estado) diff.push({ k:"Estado", from:user.estado, to:estado });

  const submit = () => {
    if (!changed) return;
    setSubmitting(true);
    setTimeout(() => {
      onSaved?.({ ...user, nombre, rol, estado });
      onClose?.();
    }, 500);
  };

  const Footer = (
    <>
      <Button variant="outline" onClick={onClose}>Cancelar</Button>
      <Button
        variant="grad"
        icon={submitting ? <LoaderIcon size={13} className="spin"/> : <CheckIcon size={13}/>}
        onClick={submit}
        disabled={!changed || submitting}
      >
        {submitting ? "Guardando…" : "Guardar cambios"}
      </Button>
    </>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Editar usuario"
      description="Modifique el rol, el estado o los datos del usuario. Los cambios quedan registrados en la auditoría."
      footer={Footer}
      width={620}
    >
      <div style={{display:"flex", flexDirection:"column", gap:16}}>
        {/* User identity card */}
        <div className="user-id-card">
          <Avatar name={user.nombre}/>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontWeight:600, fontSize:14}}>{user.nombre}</div>
            <div className="tiny mono">{user.email}</div>
          </div>
          <div style={{display:"flex", flexDirection:"column", alignItems:"flex-end", gap:4}}>
            <span className="tiny">Creado {user.creado}</span>
            <span className="tiny">Última actividad: {user.ultimo}</span>
          </div>
        </div>

        <Field label="Nombre completo">
          <Input value={nombre} onChange={e=>setNombre(e.target.value)}/>
        </Field>

        <Field label="Correo corporativo" hint="El correo no se puede modificar — sirve como identificador permanente.">
          <Input value={user.email} disabled style={{background:"#f2f4f6", color:"#515f74"}}/>
        </Field>

        <Field label="Rol del usuario">
          <RolePicker value={rol} onChange={setRol}/>
        </Field>

        <Field label="Estado de la cuenta">
          <div className="seg-control">
            {[
              { v:"Activo",   label:"Activa",   desc:"Puede iniciar sesión y operar normalmente.", tone:"ok" },
              { v:"Inactivo", label:"Inactiva", desc:"No puede iniciar sesión. Sus datos se conservan.", tone:"warn" },
            ].map(o => (
              <button
                key={o.v}
                type="button"
                className={`seg-opt ${estado === o.v ? `active tone-${o.tone}` : ""}`}
                onClick={()=>setEstado(o.v)}
              >
                <span className="seg-dot"/>
                <span style={{display:"flex", flexDirection:"column", alignItems:"flex-start", gap:2}}>
                  <span style={{fontWeight:600, fontSize:13}}>{o.label}</span>
                  <span className="tiny" style={{fontWeight:400}}>{o.desc}</span>
                </span>
              </button>
            ))}
          </div>
        </Field>

        {/* Live diff */}
        {changed && (
          <div className="settings-block" style={{borderColor:"rgba(0,74,198,0.20)", background:"rgba(219,225,255,0.18)"}}>
            <div className="eyebrow" style={{marginBottom:10, color:"#004ac6"}}>Cambios pendientes ({diff.length})</div>
            <div style={{display:"flex", flexDirection:"column", gap:6}}>
              {diff.map((d, i) => (
                <div key={i} style={{display:"flex", alignItems:"center", gap:8, fontSize:12.5}}>
                  <span className="mono" style={{color:"#515f74", minWidth:60}}>{d.k}</span>
                  <span className="mono" style={{color:"#ba1a1a", textDecoration:"line-through"}}>{d.from}</span>
                  <ChevronRightIcon size={12}/>
                  <span className="mono" style={{color:"#065f46", fontWeight:600}}>{d.to}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="extra-actions">
          <div className="extra-action">
            <KeyIcon size={14}/>
            <div style={{flex:1}}>
              <div style={{fontSize:13, fontWeight:500}}>Resetear contraseña</div>
              <div className="tiny">Envía un correo con un enlace de un solo uso.</div>
            </div>
            <Button variant="outline" size="sm">Enviar enlace</Button>
          </div>
          <div className="extra-action">
            <ClockIcon size={14}/>
            <div style={{flex:1}}>
              <div style={{fontSize:13, fontWeight:500}}>Cerrar sesiones activas</div>
              <div className="tiny">Forzar logout en todos los dispositivos del usuario.</div>
            </div>
            <Button variant="outline" size="sm">Cerrar todas</Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
};

// ─────────────────────────────────────────────────────────────
// 3. BAJA DE USUARIO (Eliminar / Desactivar)
// ─────────────────────────────────────────────────────────────
const DeactivateUserDialog = ({ open, onClose, user, onConfirm }) => {
  const [mode, setMode]   = React.useState("deactivate"); // deactivate | delete
  const [confirm, setConfirm] = React.useState("");
  const [reassign, setReassign] = React.useState("");
  const [reason, setReason] = React.useState("Renuncia / fin de relación laboral");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setMode("deactivate");
      setConfirm("");
      setReassign("");
      setReason("Renuncia / fin de relación laboral");
      setSubmitting(false);
    }
  }, [open]);

  if (!user) return null;

  const requireText = mode === "delete" ? "ELIMINAR" : "DESACTIVAR";
  const canSubmit = confirm.trim().toUpperCase() === requireText && !submitting;

  const otherUsers = (window.USERS || []).filter(u => u.id !== user.id && u.estado === "Activo");
  const hasTemplates = (user.plantillas || 0) > 0;

  const submit = () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setTimeout(() => {
      onConfirm?.({ mode, reassignTo: reassign, reason });
      onClose?.();
    }, 600);
  };

  const Footer = (
    <>
      <Button variant="outline" onClick={onClose}>Cancelar</Button>
      <Button
        variant={mode === "delete" ? "danger-solid" : "grad"}
        icon={
          submitting ? <LoaderIcon size={13} className="spin"/> :
          mode === "delete" ? <TrashIcon size={13}/> : <LogOutIcon size={13}/>
        }
        onClick={submit}
        disabled={!canSubmit}
      >
        {submitting
          ? (mode === "delete" ? "Eliminando…" : "Desactivando…")
          : (mode === "delete" ? "Eliminar permanentemente" : "Desactivar cuenta")}
      </Button>
    </>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Dar de baja al usuario"
      description="Elija cómo retirar el acceso. La desactivación es reversible; la eliminación no."
      footer={Footer}
      width={640}
    >
      <div style={{display:"flex", flexDirection:"column", gap:16}}>
        <div className="user-id-card">
          <Avatar name={user.nombre}/>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontWeight:600, fontSize:14}}>{user.nombre}</div>
            <div className="tiny mono">{user.email}</div>
          </div>
          <Pill variant={user.rol === "Admin" ? "accent" : user.rol === "Creador" ? "accent-soft" : "secondary"}>
            {user.rol}
          </Pill>
        </div>

        {/* Mode selector */}
        <div className="mode-grid">
          <button
            type="button"
            className={`mode-card ${mode==="deactivate" ? "active mode-warn" : ""}`}
            onClick={()=>{ setMode("deactivate"); setConfirm(""); }}
          >
            <div className="mode-card-head">
              <span className="mode-card-icon"><LogOutIcon size={14}/></span>
              <span className="mode-card-title">Desactivar</span>
              <span className="pill pill-warn" style={{fontSize:10}}>Recomendado</span>
            </div>
            <ul className="mode-card-list">
              <li><CheckIcon size={11}/> Bloquea el inicio de sesión inmediatamente</li>
              <li><CheckIcon size={11}/> Conserva plantillas y documentos generados</li>
              <li><CheckIcon size={11}/> Reversible — puede reactivarse en un clic</li>
            </ul>
          </button>

          <button
            type="button"
            className={`mode-card ${mode==="delete" ? "active mode-err" : ""}`}
            onClick={()=>{ setMode("delete"); setConfirm(""); }}
          >
            <div className="mode-card-head">
              <span className="mode-card-icon mode-card-icon-err"><TrashIcon size={14}/></span>
              <span className="mode-card-title">Eliminar permanentemente</span>
            </div>
            <ul className="mode-card-list">
              <li><XIcon size={11}/> Borra la cuenta del directorio</li>
              <li><XIcon size={11}/> Las plantillas deben reasignarse antes</li>
              <li><XIcon size={11}/> Acción <strong>irreversible</strong></li>
            </ul>
          </button>
        </div>

        {/* Warnings */}
        {mode === "delete" && hasTemplates && (
          <Banner variant="err" icon={<AlertCircleIcon size={16} style={{color:"#ba1a1a"}}/>}>
            <strong>{user.plantillas} plantilla{user.plantillas === 1 ? "" : "s"}</strong> pertenecen a este usuario.
            Debe reasignarlas a otro propietario antes de eliminar la cuenta.
          </Banner>
        )}
        {mode === "deactivate" && (
          <Banner variant="warn" icon={<InfoIcon size={16} style={{color:"#b45309"}}/>}>
            La cuenta se marcará como <strong>Inactiva</strong>. Sus sesiones activas se cerrarán y no podrá volver a entrar hasta que un administrador la reactive.
          </Banner>
        )}

        {/* Reassign templates (only if delete + has templates) */}
        {mode === "delete" && hasTemplates && (
          <Field
            label={<>Reasignar <strong>{user.plantillas}</strong> plantilla{user.plantillas === 1 ? "" : "s"} a</>}
            hint="El nuevo propietario heredará permisos y aparecerá como autor en las plantillas existentes."
          >
            <Select value={reassign} onChange={e=>setReassign(e.target.value)}>
              <option value="">— Seleccione un usuario —</option>
              {otherUsers.map(u => (
                <option key={u.id} value={u.email}>
                  {u.nombre} · {u.rol} · {u.email}
                </option>
              ))}
            </Select>
          </Field>
        )}

        <Field label="Motivo de la baja" hint="Quedará registrado en auditoría para futuras revisiones.">
          <Select value={reason} onChange={e=>setReason(e.target.value)}>
            <option>Renuncia / fin de relación laboral</option>
            <option>Cambio de área o responsabilidades</option>
            <option>Cuenta duplicada</option>
            <option>Incumplimiento de políticas internas</option>
            <option>Otro</option>
          </Select>
        </Field>

        <Field
          label={<>Para confirmar, escriba <span className="mono" style={{color:"#ba1a1a"}}>{requireText}</span></>}
        >
          <Input
            placeholder={requireText}
            value={confirm}
            onChange={e=>setConfirm(e.target.value)}
            style={{textTransform:"uppercase", letterSpacing:"0.04em", fontFamily:"var(--font-mono)"}}
          />
        </Field>
      </div>
    </Dialog>
  );
};

Object.assign(window, { CreateUserDialog, EditUserDialog, DeactivateUserDialog });
