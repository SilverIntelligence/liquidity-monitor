'use client'

import { useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function FuturesPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const goldRes = await fetch(`${API_URL}/v1/metal/XAU/index/latest`)
        const silverRes = await fetch(`${API_URL}/v1/metal/XAG/index/latest`)

        const gold = await goldRes.json()
        const silver = await silverRes.json()

        setData({ gold, silver })
        setLoading(false)
      } catch (err) {
        console.error('Failed to fetch futures:', err)
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-gray-600">Loading...</div>
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Futures Market</h1>
        <p className="text-gray-600">
          CME futures positioning, open interest, and term structure
        </p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800 text-sm">
          📊 <strong>Coming Soon:</strong> Dual-axis charts showing open interest and volume trends,
          with front-month settlement marks and CFTC Commitments of Traders positioning.
        </p>
      </div>

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Gold Futures (GC)</h2>
            <div className="space-y-4">
              {data.gold?.component_details?.term && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Term Structure</h3>
                  <div className="mb-2">
                    <span className="text-3xl font-bold text-blue-600">
                      {data.gold.component_details.term.score}
                    </span>
                    <span className="text-gray-500 ml-2">/ 100</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Backwardation (positive basis) indicates spot scarcity
                  </p>
                </div>
              )}
              {data.gold?.component_details?.cot && (
                <div className="pt-4 border-t">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">CoT Positioning</h3>
                  <div className="mb-2">
                    <span className="text-3xl font-bold text-blue-600">
                      {data.gold.component_details.cot.score}
                    </span>
                    <span className="text-gray-500 ml-2">/ 100</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Net managed money positioning (CFTC weekly)
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Silver Futures (SI)</h2>
            <div className="space-y-4">
              {data.silver?.component_details?.term && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Term Structure</h3>
                  <div className="mb-2">
                    <span className="text-3xl font-bold text-blue-600">
                      {data.silver.component_details.term.score}
                    </span>
                    <span className="text-gray-500 ml-2">/ 100</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Front-month basis vs spot proxy
                  </p>
                </div>
              )}
              {data.silver?.component_details?.cot && (
                <div className="pt-4 border-t">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">CoT Positioning</h3>
                  <div className="mb-2">
                    <span className="text-3xl font-bold text-blue-600">
                      {data.silver.component_details.cot.score}
                    </span>
                    <span className="text-gray-500 ml-2">/ 100</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Speculative positioning indicator
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Market Indicators</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-gray-600">
          <div>
            <h3 className="font-medium text-gray-900 mb-2">Term Structure</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li><strong>Backwardation:</strong> Spot premium over futures (tight liquidity)</li>
              <li><strong>Contango:</strong> Futures premium over spot (ample supply)</li>
              <li>Calculated as: Front month - Second month</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium text-gray-900 mb-2">CFTC Positioning</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li>Published weekly (Fridays ~3:30 PM ET)</li>
              <li>Tracks managed money (speculators) and dealers</li>
              <li>Lower net length often precedes price squeezes</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
