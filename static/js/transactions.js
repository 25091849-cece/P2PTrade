const indicator = document.querySelector('.txn-filter-indicator');

function moveIndicator(tab) {
  const container = document.querySelector('.txn-filter-tabs');
  const containerRect = container.getBoundingClientRect();
  const tabRect = tab.getBoundingClientRect();
  indicator.style.left = (tabRect.left - containerRect.left) + 'px';
  indicator.style.width = tabRect.width + 'px';
}

const initialTab = document.querySelector('.txn-filter-tab.active');
if (initialTab) moveIndicator(initialTab);

document.querySelectorAll('.txn-filter-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.txn-filter-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    moveIndicator(tab);

    const filter = tab.dataset.filter;
    const groups = {};
    document.querySelectorAll('#txn-tbody .txn-row').forEach(row => {
      const status = row.dataset.status;
      const match = filter === 'all' || (groups[filter] ? groups[filter].includes(status) : status === filter);
      const detailRow = document.getElementById(`txn-detail-${row.dataset.id}`);
      row.style.display = match ? '' : 'none';
      if (detailRow) {
        detailRow.style.display = match ? '' : 'none';
        if (!match) {
          row.classList.remove('expanded');
          detailRow.classList.remove('open');
        }
      }
    });
  });
});

document.querySelectorAll('.txn-row').forEach(row => {
  const detailRow = document.getElementById(`txn-detail-${row.dataset.id}`);
  if (!detailRow) return;

  let timer;

  function show() {
    clearTimeout(timer);
    row.classList.add('expanded');
    detailRow.classList.add('open');
  }

  function hide() {
    timer = setTimeout(() => {
      row.classList.remove('expanded');
      detailRow.classList.remove('open');
    }, 80);
  }

  row.addEventListener('mouseenter', show);
  row.addEventListener('mouseleave', hide);
  detailRow.addEventListener('mouseenter', show);
  detailRow.addEventListener('mouseleave', hide);
});
