interface CostCenterCardProps {
  title: string;
  value: string;
  pctCte: string;
  pctFact: string;
  accentColor?: string;
}

export default function CostCenterCard({
  title,
  value,
  pctCte,
  pctFact,
  accentColor = "#4fc3f7",
}: CostCenterCardProps) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{title}</p>
      <p className="text-xl font-bold text-gray-900 mb-1">{value}</p>
      <div className="h-0.5 w-8 rounded-full mb-2" style={{ backgroundColor: accentColor }} />
      <p className="text-xs text-gray-500">
        <span style={{ color: accentColor }} className="font-medium">{pctCte}% cte</span>
        {" · "}
        <span className="font-medium text-gray-400">{pctFact}% fact.</span>
      </p>
    </div>
  );
}
