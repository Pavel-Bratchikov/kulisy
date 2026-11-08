"use strict";
const initial = JSON.parse(document.getElementById('chart-data').textContent);
const charts = {};
for (const key of ['registrations', 'arrivals']) {
  const node = document.getElementById(`${key}-chart`);
  if (!node) continue;
  charts[key] = new Chart(node, {
    type: key === 'arrivals' ? 'bar' : 'line',
    data: {
      labels: initial[key].labels,
      datasets: [{
        data: initial[key].values,
        borderColor: '#36745a',
        backgroundColor: key === 'arrivals' ? '#b8cc93' : '#edf3e5',
        fill: true, tension: .35, borderWidth: 2, pointRadius: 3, borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {legend: {display: false}},
      scales: {
        y: {beginAtZero: true, ticks: {precision: 0}, grid: {color: '#edf0e9'}},
        x: {grid: {display: false}, ticks: {maxTicksLimit: 7}},
      },
    },
  });
}
setInterval(async () => {
  if (document.hidden || !navigator.onLine) return;
  try {
    const response = await fetch(document.getElementById('stats-url').dataset.url, {redirect: 'error'});
    if (!response.ok) return;
    const data = await response.json();
    for (const key of ['registered', 'arrived', 'attendance']) {
      document.querySelectorAll(`[data-metric="${key}"]`).forEach(node => node.textContent = data[key]);
    }
    for (const key of Object.keys(charts)) {
      charts[key].data.labels = data.charts[key].labels;
      charts[key].data.datasets[0].data = data.charts[key].values;
      charts[key].update();
    }
  } catch {
    // Keep the last successful aggregates when the connection is interrupted.
  }
}, 15000);
