interface FreshnessTableProps {
  status: {
    metals: {
      [key: string]: {
        name: string
        last_update: string | null
        score: number | null
        degraded: boolean
      }
    }
  }
}

export default function FreshnessTable({ status }: FreshnessTableProps) {
  const getTimeSince = (timestamp: string | null) => {
    if (!timestamp) return 'Never'

    const now = new Date()
    const then = new Date(timestamp)
    const diffMs = now.getTime() - then.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  const getFreshnessClass = (timestamp: string | null) => {
    if (!timestamp) return 'text-red-600'

    const diffMs = new Date().getTime() - new Date(timestamp).getTime()
    const diffHours = diffMs / 3600000

    if (diffHours < 2) return 'text-green-600'
    if (diffHours < 24) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Metal
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Score
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Last Update
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {Object.entries(status.metals).map(([symbol, metal]) => (
            <tr key={symbol}>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {metal.name} ({symbol})
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {metal.score !== null ? metal.score : 'N/A'}
              </td>
              <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${getFreshnessClass(metal.last_update)}`}>
                {getTimeSince(metal.last_update)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                {metal.degraded ? (
                  <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                    Degraded
                  </span>
                ) : (
                  <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                    OK
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
