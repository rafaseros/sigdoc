// SigDoc — Login screen (2 variants)

const LoginScreen = ({ variant = "A", onLogin }) => {
  const [email, setEmail] = React.useState("rafael.gallegos@clinicafoianini.com");
  const [pwd, setPwd] = React.useState("••••••••••");
  const [loading, setLoading] = React.useState(false);
  const submit = (e) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); onLogin?.(); }, 600);
  };

  if (variant === "B") {
    // Variant B — split layout, brand panel + form panel
    return (
      <div style={{minHeight:"100vh", display:"grid", gridTemplateColumns:"1.1fr 1fr"}}>
        <div style={{
          background: "linear-gradient(135deg, #001a4d 0%, #004ac6 60%, #2563eb 100%)",
          color:"#fff", padding:"48px 56px",
          display:"flex", flexDirection:"column", justifyContent:"space-between",
          position:"relative", overflow:"hidden",
        }}>
          <div style={{position:"absolute", inset:0, background: "radial-gradient(circle at 80% 20%, rgba(255,255,255,0.18), transparent 50%), radial-gradient(circle at 10% 90%, rgba(180,197,255,0.20), transparent 50%)"}}/>
          <div style={{position:"relative", display:"flex", alignItems:"center", gap:10}}>
            <span style={{width:36, height:36, borderRadius:10, background:"#fff", color:"#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:17, letterSpacing:"-0.02em"}}>S</span>
            <span style={{fontSize:21, fontWeight:700, letterSpacing:"-0.025em"}}>SigDoc</span>
          </div>
          <div style={{position:"relative"}}>
            <div style={{fontSize:13, fontWeight:600, color:"rgba(255,255,255,0.65)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:14}}>Sistema integrado de gestión de documentos</div>
            <h1 style={{fontSize:42, fontWeight:700, lineHeight:1.1, letterSpacing:"-0.025em", margin:0, marginBottom:14}}>Sus contratos,<br/>sin trabajo manual.</h1>
            <p style={{fontSize:15, lineHeight:1.5, color:"rgba(255,255,255,0.78)", margin:0, maxWidth:420}}>Suba plantillas .docx con marcadores variables y genere documentos legales en bloque, con auditoría completa.</p>
          </div>
          <div style={{position:"relative", display:"flex", gap:24, fontSize:12, color:"rgba(255,255,255,0.65)"}}>
            <span>v1.4 · estable</span>
            <span>Soporte: soporte@sigdoc.bo</span>
          </div>
        </div>
        <div style={{display:"flex", alignItems:"center", justifyContent:"center", padding:"24px 32px"}}>
          <div style={{width:"100%", maxWidth:380}}>
            <h2 style={{fontSize:26, fontWeight:700, letterSpacing:"-0.02em", margin:0, marginBottom:6}}>Iniciar sesión</h2>
            <p style={{fontSize:13.5, color:"#515f74", margin:0, marginBottom:24}}>Acceda con su cuenta corporativa.</p>
            <form onSubmit={submit} style={{display:"flex", flexDirection:"column", gap:14}}>
              <Field label="Correo electrónico">
                <Input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoFocus/>
              </Field>
              <Field label="Contraseña">
                <Input type="password" value={pwd} onChange={e=>setPwd(e.target.value)}/>
              </Field>
              <div style={{display:"flex", justifyContent:"flex-end", marginTop:-4}}>
                <span style={{fontSize:12.5, color:"#004ac6", cursor:"pointer", fontWeight:500}}>¿Olvidó su contraseña?</span>
              </div>
              <Button variant="grad" size="lg" type="submit" disabled={loading} style={{marginTop:8}}>
                {loading ? <><LoaderIcon size={14} className="spin"/>Iniciando sesión…</> : <><LoginIcon size={15}/>Iniciar sesión</>}
              </Button>
            </form>
            <div style={{textAlign:"center", marginTop:20, fontSize:12, color:"#515f74"}}>
              ¿No tiene cuenta? Contacte a su administrador.
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Variant A — refined center card (bigger, more brand presence than current)
  return (
    <div style={{minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", padding:"24px", position:"relative", overflow:"hidden"}}>
      <div style={{position:"absolute", top:"-20%", right:"-10%", width:520, height:520, borderRadius:"50%", background:"radial-gradient(circle, rgba(0,74,198,0.10), transparent 70%)", filter:"blur(20px)"}}/>
      <div style={{position:"absolute", bottom:"-15%", left:"-10%", width:480, height:480, borderRadius:"50%", background:"radial-gradient(circle, rgba(180,197,255,0.30), transparent 70%)", filter:"blur(20px)"}}/>
      <div className="card-glass" style={{width:"100%", maxWidth:440, padding:"36px 32px", position:"relative"}}>
        <div style={{textAlign:"center", marginBottom:28}}>
          <div style={{display:"inline-flex", alignItems:"center", gap:10, marginBottom:18}}>
            <span style={{width:40, height:40, borderRadius:11, background:"linear-gradient(135deg,#004ac6,#2563eb)", color:"#fff", display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:18, boxShadow:"0 6px 20px rgba(0,74,198,0.35)"}}>S</span>
            <span style={{fontSize:24, fontWeight:700, letterSpacing:"-0.025em", color:"#004ac6"}}>SigDoc</span>
          </div>
          <h1 style={{fontSize:22, fontWeight:700, letterSpacing:"-0.02em", margin:0, marginBottom:6}}>Bienvenido de vuelta</h1>
          <div style={{fontSize:13.5, color:"#515f74"}}>Inicie sesión para gestionar sus plantillas</div>
        </div>
        <form onSubmit={submit} style={{display:"flex", flexDirection:"column", gap:14}}>
          <Field label="Correo electrónico">
            <Input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoFocus/>
          </Field>
          <Field label="Contraseña">
            <Input type="password" value={pwd} onChange={e=>setPwd(e.target.value)}/>
          </Field>
          <div style={{display:"flex", justifyContent:"flex-end", marginTop:-4}}>
            <span style={{fontSize:12.5, color:"#004ac6", cursor:"pointer", fontWeight:500}}>¿Olvidó su contraseña?</span>
          </div>
          <Button variant="grad" size="lg" type="submit" disabled={loading} style={{marginTop:6}}>
            {loading ? <><LoaderIcon size={14} className="spin"/>Iniciando sesión…</> : "Iniciar sesión"}
          </Button>
        </form>
        <div style={{textAlign:"center", marginTop:22, fontSize:12, color:"#515f74", paddingTop:18, borderTop:"1px solid rgba(195,198,215,0.20)"}}>
          ¿Sin cuenta? Contacte a su administrador del sistema.
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { LoginScreen });
