interface ComponentBarsProps {
  data: {
    components: any
    component_details?: {
      [key: string]: {
        score: number
        value: number
      }
    }
  }
}

export default function ComponentBars({ data }: ComponentBarsProps) {
  const components = data.component_details || {}
  const componentNames: { [key: string]: string } = {
    'inventory': 'Inventory',
    'etf_flow': 'ETF Flows',
    'term': 'Term Structure',
    'cot': 'CoT Positioning',
    'premium': 'Dealer Premiums',
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="space-y-4">
        {Object.entries(components).map(([key, value]) => (
          <div key={key}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-sm font-medium text-gray-700">
                {componentNames[key] || key}
              </span>
              <span className="text-sm font-semibold text-gray-900">
                {value.score}/100
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${
                  value.score >= 80 ? 'bg-red-500' :
                  value.score >= 60 ? 'bg-orange-500' :
                  value.score >= 40 ? 'bg-yellow-500' :
                  value.score >= 20 ? 'bg-green-500' :
                  'bg-blue-500'
                }`}
                style={{ width: `${value.score}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
