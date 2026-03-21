"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Signal {
  ticker: string;
  name: string;
  close: number;
  strength: number;
  amount_b: number;
  ma_20: number;
  high_20: number;
  atr_20: number;
  stage: number;
}

interface MarketStatus {
  date: string;
  kospi_close: number | null;
  kospi_ma60: number | null;
  kospi_above_ma: boolean | null;
  kosdaq_close: number | null;
  kosdaq_ma60: number | null;
  kosdaq_above_ma: boolean | null;
  is_bullish: boolean | null;
}

function stageLabel(stage: number): { text: string; color: string } {
  const map: Record<number, { text: string; color: string }> = {
    1: { text: "S1 안정상승", color: "text-green-600" },
    2: { text: "S2 하락변화", color: "text-yellow-600" },
    3: { text: "S3 하락변화", color: "text-orange-600" },
    4: { text: "S4 안정하락", color: "text-red-600" },
    5: { text: "S5 상승변화", color: "text-orange-600" },
    6: { text: "S6 상승변화", color: "text-yellow-600" },
  };
  return map[stage] || { text: "S0", color: "text-gray-400" };
}

export default function Home() {
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [market, setMarket] = useState<MarketStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchSignals() {
    setLoading(true);
    setError("");
    try {
      const [sigRes, mktRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/signals/scan?date=${date}`),
        fetch(`${API_BASE}/api/v1/signals/market-status?date=${date}`),
      ]);

      if (!sigRes.ok) throw new Error(`신호 조회 실패: ${sigRes.status}`);
      const sigData = await sigRes.json();
      setSignals(sigData.signals || []);

      if (mktRes.ok) {
        const mktData = await mktRes.json();
        setMarket(mktData);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "알 수 없는 오류");
      setSignals([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      {/* 헤더 */}
      <header className="mb-8">
        <h1 className="text-3xl font-bold">TrendSurfer</h1>
        <p className="text-gray-500 mt-1">추세추종 전략 신호 대시보드</p>
      </header>

      {/* 조회 바 */}
      <div className="flex gap-4 items-end mb-6">
        <div>
          <label className="block text-sm font-medium mb-1">기준 날짜</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="border rounded px-3 py-2 bg-transparent"
          />
        </div>
        <button
          onClick={fetchSignals}
          disabled={loading}
          className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "조회 중..." : "스캔 실행"}
        </button>
      </div>

      {/* 시장 상태 */}
      {market && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="border rounded-lg p-4">
            <div className="text-sm text-gray-500">KOSPI</div>
            <div className="text-xl font-semibold">
              {market.kospi_close?.toLocaleString() ?? "-"}
            </div>
            <div className="text-sm">
              MA60: {market.kospi_ma60?.toLocaleString() ?? "-"}
              <span className="ml-2">
                {market.kospi_above_ma === true && "🟢"}
                {market.kospi_above_ma === false && "🔴"}
              </span>
            </div>
          </div>
          <div className="border rounded-lg p-4">
            <div className="text-sm text-gray-500">KOSDAQ</div>
            <div className="text-xl font-semibold">
              {market.kosdaq_close?.toLocaleString() ?? "-"}
            </div>
            <div className="text-sm">
              MA60: {market.kosdaq_ma60?.toLocaleString() ?? "-"}
              <span className="ml-2">
                {market.kosdaq_above_ma === true && "🟢"}
                {market.kosdaq_above_ma === false && "🔴"}
              </span>
            </div>
          </div>
          <div className="border rounded-lg p-4">
            <div className="text-sm text-gray-500">시장 필터</div>
            <div className="text-xl font-semibold">
              {market.is_bullish === true
                ? "🟢 상승 허용"
                : market.is_bullish === false
                ? "🔴 진입 금지"
                : "⚪ 판단 불가"}
            </div>
          </div>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>
      )}

      {/* 신호 테이블 */}
      {signals.length > 0 && (
        <div className="overflow-x-auto">
          <div className="text-sm text-gray-500 mb-2">
            {signals.length}개 종목 발견 (장중 강도순)
          </div>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b font-medium text-left">
                <th className="py-2 px-3">#</th>
                <th className="py-2 px-3">종목코드</th>
                <th className="py-2 px-3">종목명</th>
                <th className="py-2 px-3 text-right">종가</th>
                <th className="py-2 px-3 text-right">강도(%)</th>
                <th className="py-2 px-3 text-right">거래대금(억)</th>
                <th className="py-2 px-3 text-right">MA(20)</th>
                <th className="py-2 px-3 text-right">HIGH(20)</th>
                <th className="py-2 px-3 text-right">ATR(20)</th>
                <th className="py-2 px-3">Stage</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => {
                const stage = stageLabel(s.stage);
                return (
                  <tr key={s.ticker} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="py-2 px-3 text-gray-400">{i + 1}</td>
                    <td className="py-2 px-3 font-mono">{s.ticker}</td>
                    <td className="py-2 px-3 font-medium">{s.name}</td>
                    <td className="py-2 px-3 text-right">{s.close.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right text-green-600 font-medium">
                      +{s.strength}%
                    </td>
                    <td className="py-2 px-3 text-right">{s.amount_b.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right">{s.ma_20.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right">{s.high_20.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right">{s.atr_20.toLocaleString()}</td>
                    <td className={`py-2 px-3 ${stage.color}`}>{stage.text}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 빈 상태 */}
      {!loading && signals.length === 0 && !error && (
        <div className="text-center text-gray-400 py-16">
          날짜를 선택하고 &quot;스캔 실행&quot; 버튼을 눌러주세요
        </div>
      )}
    </div>
  );
}
