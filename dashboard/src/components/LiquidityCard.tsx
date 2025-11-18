interface LiquidityCardProps {
  metal: string
  data: {
    liquidity_index: number
    timestamp: string
    degraded: boolean
  }
}

export default function LiquidityCard({ metal, data }: LiquidityCardProps) {
  const getColorClass = (score: number) => {
    if (score >= 80) return 'text-red-600 bg-red-50'
    if (score >= 60) return 'text-orange-600 bg-orange-50'
    if (score >= 40) return 'text-yellow-600 bg-yellow-50'
    if (score >= 20) return 'text-green-600 bg-green-50'
    return 'text-blue-600 bg-blue-50'
  }

  const getLabel = (score: number) => {
    if (score >= 80) return 'Very Tight'
    if (score >= 60) return 'Tight'
    if (score >= 40) return 'Neutral'
    if (score >= 20) return 'Loose'
    return 'Very Loose'
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{metal}</h3>
        {data.degraded && (
          <span className="px-2 py-1 text-xs font-medium text-yellow-800 bg-yellow-100 rounded">
            Partial Data
          </span>
        )}
      </div>

      <div className="flex items-baseline space-x-2 mb-2">
        <span className={`text-5xl font-bold ${getColorClass(data.liquidity_index)}`}>
          {data.liquidity_index}
        </span>
        <span className="text-gray-500 text-sm">/ 100</span>
      </div>

      <div className="mb-4">
        <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${getColorClass(data.liquidity_index)}`}>
          {getLabel(data.liquidity_index)}
        </span>
      </div>

      <div className="text-sm text-gray-500">
        Last updated: {new Date(data.timestamp).toLocaleString()}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="text-xs text-gray-600">
          <p className="mb-1"><strong>0-20:</strong> Very loose (abundant supply)</p>
          <p className="mb-1"><strong>40-60:</strong> Neutral</p>
          <p><strong>80-100:</strong> Very tight (scarcity signals)</p>
        </div>
      </div>
    </div>
  )
}
