(function () {
  var list = document.getElementById('list');
  if (!list) return;
  var items = Array.prototype.slice.call(list.querySelectorAll('.item'));
  var $ = function (id) { return document.getElementById(id); };
  function apply() {
    var type = $('f-type').value, kg = $('f-kg').value, sort = $('f-sort').value;
    var onlyNew = $('f-new').checked, rv = $('f-rv').checked;
    var lo = 0, hi = 999;
    if (kg) { var p = kg.split('-'); lo = parseFloat(p[0]); hi = parseFloat(p[1]); }
    var shown = 0;
    items.forEach(function (el) {
      var ok = true, k = parseFloat(el.dataset.kg);
      if (type && el.dataset.types.split(' ').indexOf(type) < 0) ok = false;
      if (k < lo || k > hi) ok = false;
      if (onlyNew && el.dataset.new !== '1') ok = false;
      if (rv && parseFloat(el.dataset.review) < 4) ok = false;
      el.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    var sorted = items.slice().sort(function (a, b) {
      if (sort === 'price') return a.dataset.price - b.dataset.price;
      if (sort === 'review') return (b.dataset.review - a.dataset.review) || (b.dataset.rc - a.dataset.rc);
      return a.dataset.eff - b.dataset.eff;
    });
    sorted.forEach(function (el) { list.appendChild(el); });
    var n = 0;
    sorted.forEach(function (el) {
      var r = el.querySelector('.rank');
      if (r && el.style.display !== 'none') r.textContent = ++n;
    });
    $('f-count').textContent = shown + '件を表示中';
  }
  ['f-type', 'f-kg', 'f-sort', 'f-new', 'f-rv'].forEach(function (id) {
    var el = $(id); if (el) el.addEventListener('change', apply);
  });
  apply();
})();
