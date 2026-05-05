// Inline Lucide-style icons used across the SigDoc app.
// All 24x24 viewBox, stroke-2, currentColor.

const baseProps = {
  width: 16, height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const Icon = (paths) => ({ size = 16, className = "", style }) =>
  <svg {...baseProps} width={size} height={size} className={className} style={style}>{paths}</svg>;

const FileTextIcon = Icon(<>
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <polyline points="14 2 14 8 20 8"/>
  <line x1="16" y1="13" x2="8" y2="13"/>
  <line x1="16" y1="17" x2="8" y2="17"/>
</>);

const UploadIcon = Icon(<>
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <polyline points="17 8 12 3 7 8"/>
  <line x1="12" y1="3" x2="12" y2="15"/>
</>);

const SearchIcon = Icon(<>
  <circle cx="11" cy="11" r="7"/>
  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
</>);

const XIcon = Icon(<>
  <line x1="18" y1="6" x2="6" y2="18"/>
  <line x1="6" y1="6" x2="18" y2="18"/>
</>);

const CheckCircleIcon = Icon(<>
  <circle cx="12" cy="12" r="10"/>
  <path d="M9 12l2 2 4-4"/>
</>);

const AlertCircleIcon = Icon(<>
  <circle cx="12" cy="12" r="10"/>
  <line x1="12" y1="8" x2="12" y2="12"/>
  <line x1="12" y1="16" x2="12.01" y2="16"/>
</>);

const LoaderIcon = Icon(<>
  <path d="M21 12a9 9 0 1 1-6.22-8.56"/>
</>);

const EyeIcon = Icon(<>
  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/>
  <circle cx="12" cy="12" r="3"/>
</>);

const KeyIcon = Icon(<>
  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
</>);

const BookIcon = Icon(<>
  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
</>);

const LogOutIcon = Icon(<>
  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
  <polyline points="16 17 21 12 16 7"/>
  <line x1="21" y1="12" x2="9" y2="12"/>
</>);

const ChevronDownIcon = Icon(<>
  <polyline points="6 9 12 15 18 9"/>
</>);

const PlusIcon = Icon(<>
  <line x1="12" y1="5" x2="12" y2="19"/>
  <line x1="5" y1="12" x2="19" y2="12"/>
</>);

const TrashIcon = Icon(<>
  <polyline points="3 6 5 6 21 6"/>
  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
  <path d="M10 11v6"/><path d="M14 11v6"/>
</>);

const ChevronRightIcon = Icon(<polyline points="9 18 15 12 9 6"/>);
const ChevronLeftIcon = Icon(<polyline points="15 18 9 12 15 6"/>);
const ArrowLeftIcon = Icon(<><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></>);
const UsersIcon = Icon(<>
  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
  <circle cx="9" cy="7" r="4"/>
  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
</>);
const ShieldIcon = Icon(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>);
const FilterIcon = Icon(<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>);
const DownloadIcon = Icon(<>
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <polyline points="7 10 12 15 17 10"/>
  <line x1="12" y1="15" x2="12" y2="3"/>
</>);
const ShareIcon = Icon(<>
  <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
</>);
const EditIcon = Icon(<>
  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
</>);
const FolderIcon = Icon(<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>);
const ClockIcon = Icon(<><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>);
const TableIcon = Icon(<>
  <rect x="3" y="3" width="18" height="18" rx="2"/>
  <line x1="3" y1="9" x2="21" y2="9"/>
  <line x1="3" y1="15" x2="21" y2="15"/>
  <line x1="9" y1="3" x2="9" y2="21"/>
</>);
const SettingsIcon = Icon(<>
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
</>);
const InfoIcon = Icon(<><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>);
const CodeIcon = Icon(<><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></>);
const HistoryIcon = Icon(<>
  <path d="M3 3v5h5"/>
  <path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/>
  <line x1="12" y1="7" x2="12" y2="12"/>
  <line x1="12" y1="12" x2="15" y2="14"/>
</>);
const FileSpreadsheetIcon = Icon(<>
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <polyline points="14 2 14 8 20 8"/>
  <line x1="8" y1="13" x2="16" y2="13"/>
  <line x1="8" y1="17" x2="16" y2="17"/>
  <line x1="12" y1="13" x2="12" y2="21"/>
</>);
const SparklesIcon = Icon(<path d="M12 3l2.4 5.6L20 11l-5.6 2.4L12 19l-2.4-5.6L4 11l5.6-2.4L12 3z"/>);
const UserPlusIcon = Icon(<>
  <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
  <circle cx="8.5" cy="7" r="4"/>
  <line x1="20" y1="8" x2="20" y2="14"/>
  <line x1="23" y1="11" x2="17" y2="11"/>
</>);
const CopyIcon = Icon(<>
  <rect x="9" y="9" width="13" height="13" rx="2"/>
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</>);
const MoreIcon = Icon(<><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>);
const CheckIcon = Icon(<polyline points="20 6 9 17 4 12"/>);
const LoginIcon = Icon(<>
  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
  <polyline points="10 17 15 12 10 7"/>
  <line x1="15" y1="12" x2="3" y2="12"/>
</>);

Object.assign(window, {
  FileTextIcon, UploadIcon, SearchIcon, XIcon, CheckCircleIcon,
  AlertCircleIcon, LoaderIcon, EyeIcon, KeyIcon, BookIcon, LogOutIcon,
  ChevronDownIcon, PlusIcon, TrashIcon,
  ChevronRightIcon, ChevronLeftIcon, ArrowLeftIcon, UsersIcon, ShieldIcon,
  FilterIcon, DownloadIcon, ShareIcon, EditIcon, FolderIcon, ClockIcon,
  TableIcon, SettingsIcon, InfoIcon, CodeIcon, HistoryIcon, FileSpreadsheetIcon,
  SparklesIcon, UserPlusIcon, CopyIcon, MoreIcon, CheckIcon, LoginIcon,
});
