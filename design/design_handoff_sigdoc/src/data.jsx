// Mock data — realistic samples for SigDoc redesign demo
const NOW = "1 may 2026";

const TEMPLATES = [
  { id: "t1", nombre: "Contrato de Trabajo Indefinido", desc: "Contrato laboral estándar para personal de planta.", tipo: "Contrato", vars: 14, version: "v3", versiones: 3, fecha: "27 abr 2026", autor: "rafael.gallegos@clinicafoianini.com", shared: true, size: "97.9 KB" },
  { id: "t2", nombre: "Acuerdo de Confidencialidad (NDA)", desc: "NDA bilateral para proveedores y consultores externos.", tipo: "Acuerdo", vars: 8, version: "v1", versiones: 1, fecha: "24 abr 2026", autor: "karol.zabala@cainco.org.bo", shared: false, size: "42.3 KB" },
  { id: "t3", nombre: "Carta de Renuncia Voluntaria", desc: "Plantilla de carta de renuncia con período de aviso.", tipo: "Carta", vars: 6, version: "v2", versiones: 2, fecha: "20 abr 2026", autor: "wendy.torres@cainco.org.bo", shared: true, size: "28.1 KB" },
  { id: "t4", nombre: "Anexo de Modificación de Sueldo", desc: "Anexo para ajustes salariales y de jornada.", tipo: "Anexo", vars: 9, version: "v1", versiones: 1, fecha: "18 abr 2026", autor: "rafael.gallegos@clinicafoianini.com", shared: false, size: "33.7 KB" },
  { id: "t5", nombre: "Contrato Modelo Cursos para Empresas SRL", desc: "Contrato de capacitación CAINCO Academy a la medida.", tipo: "Contrato", vars: 17, version: "v1", versiones: 1, fecha: "27 abr 2026", autor: "karol.zabala@cainco.org.bo", shared: true, size: "97.9 KB" },
  { id: "t6", nombre: "Liquidación de Beneficios Sociales", desc: "Cálculo de finiquito y planilla de liquidación.", tipo: "Anexo", vars: 12, version: "v2", versiones: 2, fecha: "14 abr 2026", autor: "dayna.buitrago@cainco.org.bo", shared: false, size: "55.2 KB" },
];

const USERS = [
  { id:"u1", email:"rafael.gallegos@clinicafoianini.com", nombre:"José Rafael Gallegos Rojas", rol:"Admin",   estado:"Activo",  creado:"15 ene 2026", ultimo:"hoy, 14:32", plantillas: 18 },
  { id:"u2", email:"karol.zabala@cainco.org.bo",          nombre:"Karol Zabala Méndez",       rol:"Creador", estado:"Activo",  creado:"21 ene 2026", ultimo:"hoy, 11:08", plantillas: 12 },
  { id:"u3", email:"wendy.torres@cainco.org.bo",          nombre:"Wendy Torres Aguilar",      rol:"Generador", estado:"Activo", creado:"02 feb 2026", ultimo:"ayer, 17:45", plantillas: 0 },
  { id:"u4", email:"dayna.buitrago@cainco.org.bo",        nombre:"Dayna Buitrago",            rol:"Creador", estado:"Activo",  creado:"12 feb 2026", ultimo:"ayer, 09:22", plantillas: 6 },
  { id:"u5", email:"devrafaseros@gmail.com",              nombre:"Rafael Seros (Dev)",        rol:"Admin",   estado:"Activo",  creado:"05 ene 2026", ultimo:"hoy, 15:01", plantillas: 24 },
  { id:"u6", email:"luis.morales@cainco.org.bo",          nombre:"Luis Morales Aranda",       rol:"Generador", estado:"Inactivo", creado:"18 feb 2026", ultimo:"hace 12 días", plantillas: 0 },
];

const ACTION_KINDS = {
  login:           { label: "Inicio de sesión",          variant:"secondary",   icon:"Login" },
  share:           { label: "Compartir plantilla",       variant:"accent-soft", icon:"Share" },
  download:        { label: "Descarga de documento",     variant:"accent",      icon:"Download" },
  generate:        { label: "Generación individual",     variant:"ok",          icon:"Sparkles" },
  bulk:            { label: "Generación masiva",         variant:"ok",          icon:"Sparkles" },
  upload:          { label: "Subida de plantilla",       variant:"accent-soft", icon:"Upload" },
  user_create:     { label: "Creación de usuario",       variant:"warn",        icon:"UserPlus" },
  user_update:     { label: "Actualización de usuario",  variant:"warn",        icon:"Edit" },
  password_reset:  { label: "Reseteo de contraseña",     variant:"accent",      icon:"Key" },
  template_delete: { label: "Eliminación de plantilla",  variant:"err",         icon:"Trash" },
};

const AUDIT = [
  { fecha:"1 may 2026, 15:01", grupo:"Hoy",        usuario:"devrafaseros@gmail.com",      action:"login",           recurso:"user",     detalles:"Sesión iniciada desde Chrome 124", ip:"10.0.2.4" },
  { fecha:"1 may 2026, 14:59", grupo:"Hoy",        usuario:"karol.zabala@cainco.org.bo",  action:"share",           recurso:"template", detalles:"Compartida con devrafaseros@gmail.com", ip:"10.0.2.4" },
  { fecha:"1 may 2026, 14:58", grupo:"Hoy",        usuario:"karol.zabala@cainco.org.bo",  action:"login",           recurso:"user",     detalles:"Sesión iniciada", ip:"10.0.2.4" },
  { fecha:"29 abr 2026, 22:33", grupo:"Esta semana", usuario:"karol.zabala@cainco.org.bo",  action:"download",        recurso:"document", detalles:"Formato PDF · 108cc2317698", ip:"10.0.2.4" },
  { fecha:"29 abr 2026, 20:41", grupo:"Esta semana", usuario:"karol.zabala@cainco.org.bo",  action:"generate",        recurso:"document", detalles:"NOMBRE_EMPRESA.docx · 1 documento", ip:"10.0.2.4" },
  { fecha:"29 abr 2026, 15:00", grupo:"Esta semana", usuario:"karol.zabala@cainco.org.bo",  action:"login",           recurso:"user",     detalles:"Sesión iniciada", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 14:35", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"upload",          recurso:"template", detalles:"Contrato Modelo Cursos · 97.9 KB", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 06:49", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"user_update",     recurso:"user",     detalles:"role: creador → dayna.buitrago", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 06:49", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"user_create",     recurso:"user",     detalles:"email: wendy.torres@cainco.org.bo", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 06:48", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"password_reset",  recurso:"user",     detalles:"target: dayna.buitrago@cainco.org.bo", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 06:47", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"user_create",     recurso:"user",     detalles:"email: dayna.buitrago@cainco.org.bo", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 06:42", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"login",           recurso:"user",     detalles:"Sesión iniciada", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 01:55", grupo:"La semana pasada", usuario:"devrafaseros@gmail.com", action:"user_update",     recurso:"user",     detalles:"role: template_creator → rafael.gallegos", ip:"10.0.2.4" },
  { fecha:"27 abr 2026, 01:48", grupo:"La semana pasada", usuario:"karol.zabala@cainco.org.bo", action:"upload",      recurso:"template", detalles:"Contrato Modelo Cursos · v1", ip:"10.0.2.4" },
];

const TEMPLATE_VARIABLES = [
  { name:"nombre_empresa",     tipo:"texto",  apariciones:7,  hint:"Razón social de la empresa contratante" },
  { name:"numero",             tipo:"texto",  apariciones:6,  hint:"Número de NIT o matrícula de comercio" },
  { name:"ciudad",             tipo:"texto",  apariciones:2,  hint:"Ciudad donde se firma el contrato" },
  { name:"direccion",          tipo:"texto",  apariciones:1,  hint:"Dirección legal completa" },
  { name:"nombre_representante", tipo:"texto", apariciones:1, hint:"Representante legal de la empresa" },
  { name:"nombre_instructor",  tipo:"texto",  apariciones:1,  hint:"Instructor asignado al curso" },
  { name:"nombre_curso",       tipo:"texto",  apariciones:1,  hint:"Nombre completo del curso" },
  { name:"fecha_ini",          tipo:"fecha",  apariciones:1,  hint:"Fecha de inicio (DD/MM/YYYY)" },
  { name:"hora",               tipo:"texto",  apariciones:1,  hint:"Hora de inicio del curso" },
  { name:"monto_bs_usd",       tipo:"texto",  apariciones:1,  hint:"Moneda del monto: Bs. o USD" },
  { name:"monto_numeral",      tipo:"número", apariciones:1,  hint:"Monto en formato numérico" },
  { name:"monto_literal",      tipo:"texto",  apariciones:1,  hint:"Monto escrito en letras" },
  { name:"numero_cuenta_bancaria", tipo:"texto", apariciones:1, hint:"Número de cuenta de la empresa" },
  { name:"nombre_banco",       tipo:"texto",  apariciones:1,  hint:"Banco donde se realizará el pago" },
  { name:"caja_ahorro_corriente", tipo:"texto", apariciones:1, hint:"Caja de ahorro o cuenta corriente" },
  { name:"dia_mes_ano",        tipo:"fecha",  apariciones:1,  hint:"Fecha de firma" },
  { name:"fecha",              tipo:"fecha",  apariciones:1,  hint:"Fecha del documento" },
];

const VERSIONS = [
  { v:"v3", uploadedBy:"rafael.gallegos@clinicafoianini.com", fecha:"27 abr 2026, 01:48 a.m.", size:"97.9 KB", vars:17, current:true,  notes:"Ajuste de cláusula octava — vigencia." },
  { v:"v2", uploadedBy:"rafael.gallegos@clinicafoianini.com", fecha:"15 abr 2026, 18:22",       size:"96.4 KB", vars:16, current:false, notes:"Agregado de NIT y matrícula de comercio." },
  { v:"v1", uploadedBy:"karol.zabala@cainco.org.bo",          fecha:"08 abr 2026, 14:11",       size:"94.1 KB", vars:14, current:false, notes:"Versión inicial subida desde Word." },
];

const SHARED_WITH = [
  { email:"devrafaseros@gmail.com",       fecha:"1 may 2026",  acceso:"Lectura" },
  { email:"wendy.torres@cainco.org.bo",   fecha:"28 abr 2026", acceso:"Lectura" },
];

const DOCUMENTS_GEN = [
  { id:"d1", archivo:"NOMBRE_EMPRESA.docx",        tipo:"Individual", fecha:"29 abr 2026, 20:41", autor:"karol.zabala@cainco.org.bo", size:"112 KB" },
  { id:"d2", archivo:"Cainco_Lote_29abr.zip",      tipo:"Masiva",     fecha:"29 abr 2026, 18:04", autor:"karol.zabala@cainco.org.bo", size:"3.2 MB", count: 18 },
  { id:"d3", archivo:"Foianini_RRHH_marzo.zip",    tipo:"Masiva",     fecha:"21 abr 2026, 09:55", autor:"rafael.gallegos@clinicafoianini.com", size:"1.8 MB", count: 9 },
];

Object.assign(window, { TEMPLATES, USERS, AUDIT, ACTION_KINDS, TEMPLATE_VARIABLES, VERSIONS, SHARED_WITH, DOCUMENTS_GEN });
