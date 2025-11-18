'use client'

import { useEffect, useState } from 'react'
import LiquidityCard from '@/components/LiquidityCard'
import ComponentBars from '@/components/ComponentBars'
import FreshnessTable from '@/components/FreshnessTable'
import HistoryChart from '@/components/HistoryChart'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface IndexData {
  metal: string
  timestamp: string
  liquidity_index: number
  components: any
  degraded: boolean
}

interface StatusData {
  ok: boolean
  timestamp: string
  metals: {
    [key: string]: {
      name: string
      last_update: string | null
      score: number | null
      degraded: boolean
    }
  }
}

export default function Home() {
  const [goldIndex, setGoldIndex] = useState<IndexData | null>(null)
  const [silverIndex, setSilverIndex] = useState<IndexData | null>(null)
  const [status, setStatus] = useState<StatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch status
        const statusRes = await fetch(`${API_URL}/v1/status`)
        const statusData = await statusRes.json()
        setStatus(statusData)

        // Fetch Gold index
        try {
          const goldRes = await fetch(`${API_URL}/v1/metal/XAU/index/latest`)
          const goldData = await goldRes.json()
          setGoldIndex(goldData)
        } catch (err) {
          console.error('Gold data not available')
        }

        // Fetch Silver index
        try {
          const silverRes = await fetch(`${API_URL}/v1/metal/XAG/index/latest`)
          const silverData = await silverRes.json()
          setSilverIndex(silverData)
        } catch (err) {
          console.error('Silver data not available')
        }

        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data')
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Liquidity Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {goldIndex && <LiquidityCard metal="Gold (XAU)" data={goldIndex} />}
          {silverIndex && <LiquidityCard metal="Silver (XAG)" data={silverIndex} />}
        </div>
      </div>

      {goldIndex && (
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Gold Component Scores</h2>
          <ComponentBars data={goldIndex} />
        </div>
      )}

      {silverIndex && (
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Silver Component Scores</h2>
          <ComponentBars data={silverIndex} />
        </div>
      )}

      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Historical Trends (30 Days)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <HistoryChart metal="XAU" title="Gold Liquidity Index" />
          <HistoryChart metal="XAG" title="Silver Liquidity Index" />
        </div>
      </div>

      {status && (
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Data Freshness</h2>
          <FreshnessTable status={status} />
        </div>
      )}
    </div>
  )
}
