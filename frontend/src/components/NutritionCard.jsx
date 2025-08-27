import React from 'react'

export default function NutritionCard({ data }){
  // data: { food, quantity, unit, calories, protein_g, carbs_g, fats_g, micros: { ... } }
  return (
    <div className="nutri-card p-3 mt-2">
      <div className="d-flex justify-content-between align-items-center">
        <h5 className="mb-1">{data.food}</h5>
        <span className="badge nutri-badge">{data.quantity} {data.unit || 'g'}</span>
      </div>
      <div className="row g-2 mt-2">
        {[
          ['Calories', data.calories],
          ['Protein (g)', data.protein_g],
          ['Carbs (g)', data.carbs_g],
          ['Fats (g)', data.fats_g],
        ].map(([k,v]) => (
          <div className="col-6 col-md-3" key={k}>
            <div className="p-2 border rounded-3 text-center" style={{borderColor:'#2a3a78'}}>
              <div className="small text-secondary">{k}</div>
              <div className="fs-5 fw-semibold">{v ?? '—'}</div>
            </div>
          </div>
        ))}
      </div>
      {data.micros && (
        <div className="mt-3">
          <div className="small text-secondary mb-1">Micronutrients (approx.)</div>
          <div className="d-flex flex-wrap gap-2">
            {Object.entries(data.micros).map(([k,v])=> (
              <span className="badge nutri-badge" key={k}>{k}: {v}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}