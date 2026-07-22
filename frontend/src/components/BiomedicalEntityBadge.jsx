const TYPE_STYLES = {
  gene: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  disease: 'bg-rose-50 text-rose-700 border-rose-200',
  drug: 'bg-blue-50 text-blue-700 border-blue-200',
}

const DEFAULT_STYLE = 'bg-slate-100 text-slate-700 border-slate-200'

function BiomedicalEntityBadge({ entity }) {
  const style = TYPE_STYLES[entity.type] || DEFAULT_STYLE

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${style}`}>
      {entity.text}
      <span className="ml-1.5 text-[10px] uppercase tracking-wide opacity-70">{entity.type}</span>
    </span>
  )
}

export default BiomedicalEntityBadge
