/**
 * P2PTrade Marketplace JavaScript Module
 * Handles real-time calculations, validations, and countdown timers
 */

const Marketplace = {
  /**
   * Initialize marketplace countdown timers
   */
  initCountdownTimers() {
    const countdowns = document.querySelectorAll('[data-expires]');

    const updateTimer = (el) => {
      const expiresAt = new Date(el.dataset.expires).getTime();
      const now = new Date().getTime();
      const remaining = expiresAt - now;

      if (remaining <= 0) {
        el.textContent = 'Expired';
        el.classList.add('text-red-400');
        return false;
      }

      const hours = Math.floor(remaining / (1000 * 60 * 60));
      const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
      el.textContent = `${hours}h ${minutes}m remaining`;
      return true;
    };

    countdowns.forEach(updateTimer);
    setInterval(() => countdowns.forEach(updateTimer), 60000); // Update every minute
  },

  /**
   * Initialize create deal form validation and real-time calculations
   */
  initCreateDealForm() {
    const form = document.querySelector('form[method="POST"]');
    if (!form) return;

    const fromCurrency = document.getElementById('fromCurrency');
    const toCurrency = document.getElementById('toCurrency');
    const amountInput = document.getElementById('amountInput');
    const rateInput = document.getElementById('rateInput');
    const durationRadios = document.querySelectorAll('input[name="duration"]');

    // Get user balances from the page (injected into template)
    const userBalances = window.userBalances || {};

    const updateDealSummary = () => {
      const fromCurr = fromCurrency.value;
      const amount = parseFloat(amountInput.value) || 0;
      const rate = parseFloat(rateInput.value) || 0;
      const duration = document.querySelector('input[name="duration"]:checked').value;

      // Update offer summary
      const summaryOffer = document.getElementById('summaryOffer');
      if (fromCurr && amount > 0) {
        summaryOffer.textContent = `${amount.toFixed(2)} ${fromCurr}`;
      } else {
        summaryOffer.innerHTML = '— <span class="text-gray-400">enter amount</span>';
      }

      // Update receive summary
      const summaryReceive = document.getElementById('summaryReceive');
      if (rate > 0 && amount > 0) {
        const receiveAmount = (amount / rate).toFixed(2);
        const toCurr = toCurrency.value || 'to currency';
        summaryReceive.textContent = `${receiveAmount} ${toCurr}`;
      } else {
        summaryReceive.innerHTML = '— <span class="text-gray-400">enter rate</span>';
      }

      // Update duration
      const durationMap = {
        1: '1 hour',
        6: '6 hours',
        12: '12 hours',
        24: '24 hours',
        48: '48 hours'
      };
      const summaryDuration = document.getElementById('summaryDuration');
      summaryDuration.textContent = durationMap[duration] || '48 hours';
    };

    const validateBalance = () => {
      const fromCurr = fromCurrency.value;
      const amount = parseFloat(amountInput.value) || 0;
      const insufficientWarning = document.getElementById('insufficientWarning');
      const sufficientBalance = document.getElementById('sufficientBalance');
      const balanceInfo = document.getElementById('balanceInfo');

      insufficientWarning.classList.remove('show');
      sufficientBalance.classList.remove('show');

      if (!fromCurr) {
        balanceInfo.textContent = 'Select a currency to see available balance';
        return;
      }

      const availableBalance = userBalances[fromCurr] || 0;
      balanceInfo.innerHTML = `Available balance: <strong>${availableBalance.toFixed(2)} ${fromCurr}</strong>`;

      if (amount > 0) {
        if (amount > availableBalance) {
          insufficientWarning.classList.add('show');
        } else {
          sufficientBalance.classList.add('show');
        }
      }
    };

    // Event listeners
    fromCurrency.addEventListener('change', () => {
      validateBalance();
      updateDealSummary();
    });

    amountInput.addEventListener('input', () => {
      validateBalance();
      updateDealSummary();
    });

    rateInput.addEventListener('input', updateDealSummary);
    toCurrency.addEventListener('change', updateDealSummary);
    durationRadios.forEach(radio => {
      radio.addEventListener('change', updateDealSummary);
    });

    // Initial update
    updateDealSummary();
  },

  /**
   * Initialize deal card modals
   */
  initDealModals() {
    const dealCardBtns = document.querySelectorAll('.deal-card-btn');

    dealCardBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const modalId = btn.dataset.dealModal;
        const modal = document.getElementById(modalId);
        if (modal) {
          modal.showModal();
        }
      });
    });

    // Close modal handlers
    const closeButtons = document.querySelectorAll('.deal-modal-close');
    const cancelButtons = document.querySelectorAll('.deal-modal-cancel');

    closeButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modal = btn.closest('dialog');
        if (modal) {
          modal.close();
        }
      });
    });

    cancelButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const modal = btn.closest('dialog');
        if (modal) {
          modal.close();
        }
      });
    });

    // Close modal when clicking outside (on backdrop)
    const modals = document.querySelectorAll('.deal-modal');
    modals.forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          modal.close();
        }
      });
    });
  },

  /**
   * Initialize accept deal buttons (if using AJAX instead of form submit)
   */
  initAcceptDealButtons() {
    const acceptButtons = document.querySelectorAll('[data-accept-deal]');

    acceptButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();

        const dealId = this.dataset.acceptDeal;
        const form = this.closest('form');

        if (!form) return;

        form.submit();
      });
    });
  },

  /**
   * Format currency values
   */
  formatCurrency(value, currency) {
    return `${parseFloat(value).toFixed(2)} ${currency}`;
  },

  /**
   * Initialize all marketplace features
   */
  init() {
    this.initCountdownTimers();
    this.initCreateDealForm();
    this.initAcceptDealButtons();
    this.initDealModals();
  }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  Marketplace.init();
});
