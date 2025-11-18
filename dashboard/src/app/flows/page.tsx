'use client'

import { useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function FlowsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        // In future, this would fetch from /liquidity/etf_flows endpoint
        // For now, show component data from index
        const goldRes = await fetch(`${API_URL}/v1/metal/XAU/index/latest`)
        const silverRes = await fetch(`${API_URL}/v1/metal/XAG/index/latest`)

        const gold = await goldRes.json()
        const silver = await silverRes.json()

        setData({ gold, silver })
        setLoading(false)
      } catch (err) {
        console.error('Failed to fetch flows:', err)
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
        <h1 className="text-3xl font-bold text-gray-900 mb-2">ETF Flows</h1>
        <p className="text-gray-600">
          Daily net flows for major gold and silver ETFs (GLD, IAU, SLV, PSLV)
        </p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800 text-sm">
          📊 <strong>Coming Soon:</strong> Detailed ETF flow charts with 7-day rolling averages and historical trends.
          Currently showing component scores from the liquidity index.
        </p>
      </div>

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Gold ETFs</h2>
            {data.gold?.component_details?.etf_flow && (
              <div>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-blue-600">
                    {data.gold.component_details.etf_flow.score}
                  </span>
                  <span className="text-gray-500 ml-2">/ 100</span>
                </div>
                <p className="text-sm text-gray-600">
                  Component score reflecting ETF flow conditions
                </p>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Silver ETFs</h2>
            {data.silver?.component_details?.etf_flow && (
              <div>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-blue-600">
                    {data.silver.component_details.etf_flow.score}
                  </span>
                  <span className="text-gray-500 ml-2">/ 100</span>
                </div>
                <p className="text-sm text-gray-600">
                  Component score reflecting ETF flow conditions
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">About ETF Flows</h2>
        <div className="prose prose-sm text-gray-600">
          <p className="mb-3">
            ETF flows track the daily change in holdings for major precious metals ETFs:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li><strong>GLD</strong> - SPDR Gold Shares</li>
            <li><strong>IAU</strong> - iShares Gold Trust</li>
            <li><strong>SLV</strong> - iShares Silver Trust</li>
            <li><strong>PSLV</strong> - Sprott Physical Silver Trust</li>
          </ul>
          <p className="mt-3">
            Outflows (negative) typically indicate tighter liquidity as institutional investors
            redeem shares for physical delivery, while inflows suggest preference for paper exposure.
          </p>
        </div>
      </div>
    </div>
  )
}
