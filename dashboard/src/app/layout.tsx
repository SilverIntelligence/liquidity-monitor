import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Precious Metals Liquidity Monitor',
  description: 'Real-time liquidity monitoring for gold and silver markets',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50">
        <nav className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  Precious Metals Liquidity Monitor
                </h1>
              </div>
              <div className="flex space-x-4">
                <a href="/" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Overview
                </a>
                <a href="/flows" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  ETF Flows
                </a>
                <a href="/futures" className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Futures
                </a>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="bg-white border-t mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <p className="text-sm text-gray-500 text-center">
              Data sourced from: CME Group, CFTC, LBMA, SPDR Gold Shares, iShares, Sprott
            </p>
          </div>
        </footer>
      </body>
    </html>
  )
}
