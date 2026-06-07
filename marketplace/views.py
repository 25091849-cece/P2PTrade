from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from datetime import timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, CharFilter

from marketplace.models import Deal, Transaction
from marketplace.serializers import DealSerializer, TransactionSerializer
from marketplace.services import DealService, PaymentService
from core.models import Currency
from core.exceptions import InsufficientBalanceError, InvalidTransactionError, DealExpiredError
from wallets.models import WalletBalance
import json


# ============================================================================
# TEMPLATE VIEWS
# ============================================================================

@login_required
def index(request):
    """Marketplace index page - displays active deals."""
    from_currency = request.GET.get('from_currency')
    to_currency = request.GET.get('to_currency')

    deals = Deal.objects.filter(status='active').select_related('seller', 'from_currency', 'to_currency')

    if from_currency:
        deals = deals.filter(from_currency__code=from_currency)
    if to_currency:
        deals = deals.filter(to_currency__code=to_currency)

    deals = deals.order_by('-created_at')
    currencies = Currency.objects.all().order_by('code')

    context = {
        'deals': deals,
        'currencies': currencies,
        'selected_from': from_currency,
        'selected_to': to_currency,
    }
    return render(request, 'marketplace/index.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def create_deal(request):
    """Create a new deal offering."""
    if request.method == 'POST':
        try:
            from_currency_code = request.POST.get('from_currency')
            to_currency_code = request.POST.get('to_currency')
            amount = Decimal(request.POST.get('amount', '0'))
            rate = Decimal(request.POST.get('rate', '0'))
            trend = request.POST.get('trend', 'up')
            duration_hours = int(request.POST.get('duration', '48'))

            # Validate inputs
            if not all([from_currency_code, to_currency_code, amount, rate]):
                messages.error(request, 'All fields are required.')
                raise ValueError("Missing required fields")

            # Get currencies
            from_currency = get_object_or_404(Currency, code=from_currency_code)
            to_currency = get_object_or_404(Currency, code=to_currency_code)

            if from_currency == to_currency:
                messages.error(request, 'From and to currencies must be different.')
                raise ValueError("Same currency selected")

            # Check user has sufficient balance
            try:
                wallet_balance = request.user.wallet.balances.get(currency=from_currency)
                if wallet_balance.amount < amount:
                    messages.error(
                        request,
                        f'Insufficient {from_currency_code} balance. '
                        f'Need {amount}, have {wallet_balance.amount}'
                    )
                    raise InsufficientBalanceError(f"Insufficient balance in {from_currency_code}")
            except WalletBalance.DoesNotExist:
                messages.error(request, f'No {from_currency_code} balance found in your wallet.')
                raise

            # Create deal with custom duration
            deal = Deal.objects.create(
                seller=request.user,
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                rate=rate,
                trend=trend,
                status='active',
                expires_at=timezone.now() + timedelta(hours=duration_hours)
            )

            # Reserve wallet balance for this deal
            wallet_balance.subtract_balance(amount)
            deal.balance_reserved = True
            deal.save()

            # Create transaction record for "Deal Created"
            Transaction.objects.create(
                seller=request.user,
                user=request.user,
                deal=deal,
                type='exchange',
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                rate=rate,
                status='completed',
                payment_reference=f'DEAL{deal.id}',
                completed_at=timezone.now()
            )

            # Redirect to success page
            return redirect('marketplace:deal_created', deal_id=deal.id)

        except Exception as e:
            messages.error(request, str(e))

    currencies = Currency.objects.all().order_by('code')
    user_wallet_balances = request.user.wallet.balances.select_related('currency').all()

    # Format balances as dictionary for JavaScript
    balances_dict = {b.currency.code: float(b.amount) for b in user_wallet_balances}

    context = {
        'currencies': currencies,
        'user_balances': json.dumps(balances_dict),
    }
    return render(request, 'marketplace/create.html', context)


@login_required
def deal_created(request, deal_id):
    """Success page after creating a deal."""
    deal = get_object_or_404(Deal, id=deal_id, seller=request.user)

    # Calculate duration
    created_at = deal.created_at.timestamp()
    expires_at = deal.expires_at.timestamp()
    duration_seconds = expires_at - created_at
    duration_hours = int(duration_seconds / 3600)

    context = {
        'deal': deal,
        'receive_amount': deal.get_receive_amount(),
        'duration_hours': duration_hours,
    }
    return render(request, 'marketplace/deal_created.html', context)

@login_required
@require_http_methods(["GET"])
def confirm_accept(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    wallet = request.user.wallet

    required_amount = Decimal(str(deal.get_receive_amount()))

    try:
        buyer_balance = wallet.balances.get(
            currency=deal.to_currency
        ).amount
    except WalletBalance.DoesNotExist:
        buyer_balance = Decimal("0.00")

    return render(
        request,
        'marketplace/confirm_accept.html',
        {
            'deal': deal,
            'wallet_balance': buyer_balance,
            'required_amount': required_amount,
            'shortfall': max(
                Decimal("0.00"),
                required_amount - buyer_balance
            ),
            'enough_balance': buyer_balance >= required_amount,
        }
    )

@login_required
@require_http_methods(["POST"])
def accept_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    try:
        # This will check balance inside service and deduct
        buyer_txn, seller_txn = DealService.accept_deal(deal, request.user)
        messages.success(request, f'Deal accepted! Reference: {buyer_txn.payment_reference}')
        return redirect('transactions:index')
    except InsufficientBalanceError:
        messages.error(request, 'Insufficient wallet balance. Please top up.')
        return redirect('marketplace:index')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('marketplace:index')

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

@login_required
@require_POST
def cancel_deal(request, deal_id):
    deal = get_object_or_404(
        Deal,
        id=deal_id,
        seller=request.user
    )

    if deal.status != 'active':
        messages.error(request, "Only active deals can be cancelled.")
        return redirect('marketplace:index')

    # Return reserved balance if necessary
    if deal.balance_reserved:
        wallet_balance = request.user.wallet.balances.get(
            currency=deal.from_currency
        )

        wallet_balance.add_balance(deal.amount)
        deal.balance_reserved = False

    deal.status = 'cancelled'
    deal.save(update_fields=['status', 'balance_reserved'])

    messages.success(request, "Deal cancelled successfully.")
    return redirect('marketplace:index')

# ============================================================================
# REST API VIEWSETS
# ============================================================================

class DealFilter(FilterSet):
    """Filters for Deal model."""
    from_currency = CharFilter(field_name='from_currency__code', lookup_expr='iexact')
    to_currency = CharFilter(field_name='to_currency__code', lookup_expr='iexact')

    class Meta:
        model = Deal
        fields = ['from_currency', 'to_currency', 'status']


class DealViewSet(viewsets.ModelViewSet):
    """REST API ViewSet for Deal model."""
    serializer_class = DealSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DealFilter
    search_fields = ['seller__name', 'seller__email', 'from_currency__code', 'to_currency__code']
    ordering_fields = ['created_at', 'amount', 'rate']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get deals for listing - only active/accepted deals for browsing."""
        if self.action == 'list':
            return Deal.objects.filter(status='active').select_related(
                'seller', 'from_currency', 'to_currency'
            ).order_by('-created_at')
        elif self.action == 'my_deals':
            return Deal.objects.filter(seller=self.request.user).select_related(
                'from_currency', 'to_currency'
            ).order_by('-created_at')
        return Deal.objects.select_related('seller', 'from_currency', 'to_currency')

    def create(self, request, *args, **kwargs):
        """Create a new deal."""
        try:
            from_currency_code = request.data.get('from_currency')
            to_currency_code = request.data.get('to_currency')
            amount = Decimal(str(request.data.get('amount', '0')))
            rate = Decimal(str(request.data.get('rate', '0')))
            trend = request.data.get('trend', 'up')
            duration_hours = int(request.data.get('duration_hours', 48))

            # Validate
            if duration_hours not in [1, 6, 12, 24, 48]:
                return Response(
                    {'error': 'Duration must be 1, 6, 12, 24, or 48 hours'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get currencies
            from_currency = Currency.objects.get(code=from_currency_code)
            to_currency = Currency.objects.get(code=to_currency_code)

            if from_currency == to_currency:
                return Response(
                    {'error': 'From and to currencies must be different'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check balance
            wallet_balance = request.user.wallet.balances.get(currency=from_currency)
            if wallet_balance.amount < amount:
                return Response(
                    {'error': f'Insufficient {from_currency_code} balance'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create deal and reserve balance
            deal = Deal.objects.create(
                seller=request.user,
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                rate=rate,
                trend=trend,
                status='active',
                expires_at=timezone.now() + timedelta(hours=duration_hours)
            )

            # Reserve wallet balance
            wallet_balance.subtract_balance(amount)
            deal.balance_reserved = True
            deal.save()

            # Create transaction record
            Transaction.objects.create(
                seller=request.user,
                user=request.user,
                deal=deal,
                type='exchange',
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                rate=rate,
                status='completed',
                payment_reference=f'DEAL{deal.id}',
                completed_at=timezone.now()
            )

            serializer = self.get_serializer(deal)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Currency.DoesNotExist:
            return Response({'error': 'Currency not found'}, status=status.HTTP_400_BAD_REQUEST)
        except WalletBalance.DoesNotExist:
            return Response(
                {'error': 'Wallet balance not found for selected currency'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='my-deals')
    def my_deals(self, request):
        """Get current user's deals."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """Accept a deal."""
        try:
            deal = self.get_object()

            if deal.is_expired():
                return Response(
                    {'error': 'Deal has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if deal.status != 'active':
                return Response(
                    {'error': 'Deal is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if deal.seller == request.user:
                return Response(
                    {'error': 'Cannot accept your own deal'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            buyer_txn, seller_txn = DealService.accept_deal(deal, request.user)

            return Response({
                'success': True,
                'message': 'Deal accepted successfully',
                'payment_reference': buyer_txn.payment_reference,
                'transaction_id': buyer_txn.id
            }, status=status.HTTP_200_OK)

        except InsufficientBalanceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DealExpiredError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@login_required
@require_http_methods(["POST"])
def accept_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)

    try:
        buyer_txn, seller_txn = DealService.accept_deal(
            deal,
            request.user
        )

        messages.success(
            request,
            f"Deal accepted! Reference: {buyer_txn.payment_reference}"
        )

        return redirect("transactions:index")

    except InsufficientBalanceError:
        messages.error(
            request,
            "Insufficient wallet balance. Please top up."
        )
        return redirect("marketplace:index")

    except Exception as e:
        messages.error(request, str(e))
        return redirect("marketplace:index")

# ============================================================================
# REST API VIEWSETS
# ============================================================================

class DealFilter(FilterSet):
    """Filters for Deal model."""
    from_currency = CharFilter(field_name='from_currency__code', lookup_expr='iexact')
    to_currency = CharFilter(field_name='to_currency__code', lookup_expr='iexact')

    class Meta:
        model = Deal
        fields = ['from_currency', 'to_currency', 'status']


class DealViewSet(viewsets.ModelViewSet):
    """REST API ViewSet for Deal model."""
    serializer_class = DealSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DealFilter
    search_fields = ['seller__name', 'seller__email', 'from_currency__code', 'to_currency__code']
    ordering_fields = ['created_at', 'amount', 'rate']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get deals for listing - only active/accepted deals for browsing."""
        if self.action == 'list':
            return Deal.objects.filter(status='active').select_related(
                'seller', 'from_currency', 'to_currency'
            ).order_by('-created_at')
        elif self.action == 'my_deals':
            return Deal.objects.filter(seller=self.request.user).select_related(
                'from_currency', 'to_currency'
            ).order_by('-created_at')
        return Deal.objects.select_related('seller', 'from_currency', 'to_currency')

    def create(self, request, *args, **kwargs):
        """Create a new deal."""
        try:
            from_currency_code = request.data.get('from_currency')
            to_currency_code = request.data.get('to_currency')
            amount = Decimal(str(request.data.get('amount', '0')))
            rate = Decimal(str(request.data.get('rate', '0')))
            trend = request.data.get('trend', 'up')
            duration_hours = int(request.data.get('duration_hours', 48))

            # Validate
            if duration_hours not in [1, 6, 12, 24, 48]:
                return Response(
                    {'error': 'Duration must be 1, 6, 12, 24, or 48 hours'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get currencies
            from_currency = Currency.objects.get(code=from_currency_code)
            to_currency = Currency.objects.get(code=to_currency_code)

            if from_currency == to_currency:
                return Response(
                    {'error': 'From and to currencies must be different'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check balance
            wallet_balance = request.user.wallet.balances.get(currency=from_currency)
            if wallet_balance.amount < amount:
                return Response(
                    {'error': f'Insufficient {from_currency_code} balance'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create deal
            deal = Deal.objects.create(
                seller=request.user,
                from_currency=from_currency,
                to_currency=to_currency,
                amount=amount,
                rate=rate,
                trend=trend,
                status='active',
                expires_at=timezone.now() + timedelta(hours=duration_hours)
            )

            serializer = self.get_serializer(deal)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Currency.DoesNotExist:
            return Response({'error': 'Currency not found'}, status=status.HTTP_400_BAD_REQUEST)
        except WalletBalance.DoesNotExist:
            return Response(
                {'error': 'Wallet balance not found for selected currency'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='my-deals')
    def my_deals(self, request):
        """Get current user's deals."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """Accept a deal."""
        try:
            deal = self.get_object()

            if deal.is_expired():
                return Response(
                    {'error': 'Deal has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if deal.status != 'active':
                return Response(
                    {'error': 'Deal is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if deal.seller == request.user:
                return Response(
                    {'error': 'Cannot accept your own deal'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            buyer_txn, seller_txn = DealService.accept_deal(deal, request.user)

            return Response({
                'success': True,
                'message': 'Deal accepted successfully',
                'payment_reference': buyer_txn.payment_reference,
                'transaction_id': buyer_txn.id
            }, status=status.HTTP_200_OK)

        except InsufficientBalanceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DealExpiredError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

