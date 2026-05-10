from django.core.management.base import BaseCommand
from core.models import Currency, ExchangeRate
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate currencies and exchange rates for the P2P Trade platform'

    def handle(self, *args, **options):
        # Currency data
        currencies_data = [
            {'code': 'MYR', 'name': 'Malaysian Ringgit', 'symbol': 'RM'},
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥'},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$'},
            {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF'},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥'},
            {'code': 'HKD', 'name': 'Hong Kong Dollar', 'symbol': 'HK$'},
            {'code': 'NZD', 'name': 'New Zealand Dollar', 'symbol': 'NZ$'},
        ]

        # Create currencies
        created_count = 0
        for currency_data in currencies_data:
            currency, created = Currency.objects.get_or_create(**currency_data)
            if created:
                created_count += 1
                self.stdout.write(f'[OK] Created currency: {currency.code} - {currency.name}')
            else:
                self.stdout.write(f'[--] Currency already exists: {currency.code}')

        self.stdout.write(self.style.SUCCESS(f'\n[OK] Total currencies created: {created_count}'))

        # Create some sample exchange rates (MYR as base currency)
        # Exchange rates (approximate, as of May 2026 in this scenario)
        exchange_rates_data = [
            ('MYR', 'USD', Decimal('0.2170'), Decimal('0.5')),
            ('USD', 'MYR', Decimal('4.6083'), Decimal('-0.5')),
            ('MYR', 'EUR', Decimal('0.1980'), Decimal('0.2')),
            ('EUR', 'MYR', Decimal('5.0505'), Decimal('-0.2')),
            ('MYR', 'GBP', Decimal('0.1710'), Decimal('0.1')),
            ('GBP', 'MYR', Decimal('5.8479'), Decimal('-0.1')),
            ('USD', 'EUR', Decimal('0.9132'), Decimal('0.3')),
            ('EUR', 'USD', Decimal('1.0949'), Decimal('-0.3')),
            ('USD', 'GBP', Decimal('0.7882'), Decimal('0.2')),
            ('GBP', 'USD', Decimal('1.2687'), Decimal('-0.2')),
            ('MYR', 'JPY', Decimal('31.1'), Decimal('0.4')),
            ('JPY', 'MYR', Decimal('0.0321'), Decimal('-0.4')),
            ('MYR', 'AUD', Decimal('0.3263'), Decimal('0.1')),
            ('AUD', 'MYR', Decimal('3.0645'), Decimal('-0.1')),
            ('MYR', 'CAD', Decimal('0.2953'), Decimal('0.2')),
            ('CAD', 'MYR', Decimal('3.3869'), Decimal('-0.2')),
            ('MYR', 'CHF', Decimal('0.1895'), Decimal('0.0')),
            ('CHF', 'MYR', Decimal('5.2765'), Decimal('0.0')),
            ('MYR', 'CNY', Decimal('1.5770'), Decimal('0.3')),
            ('CNY', 'MYR', Decimal('0.6341'), Decimal('-0.3')),
            ('MYR', 'HKD', Decimal('1.6973'), Decimal('0.1')),
            ('HKD', 'MYR', Decimal('0.5891'), Decimal('-0.1')),
            ('MYR', 'NZD', Decimal('0.3574'), Decimal('0.2')),
            ('NZD', 'MYR', Decimal('2.7979'), Decimal('-0.2')),
        ]

        rate_count = 0
        for from_code, to_code, rate, change_percent in exchange_rates_data:
            try:
                from_currency = Currency.objects.get(code=from_code)
                to_currency = Currency.objects.get(code=to_code)

                exchange_rate, created = ExchangeRate.objects.update_or_create(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    defaults={'rate': rate, 'change_percent': change_percent}
                )

                if created:
                    rate_count += 1
                    self.stdout.write(f'[OK] Created exchange rate: {from_code} -> {to_code} = {rate}')
                else:
                    self.stdout.write(f'[--] Exchange rate updated: {from_code} -> {to_code} = {rate}')
            except Currency.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'[ERROR] Currency not found: {from_code} or {to_code}'))

        self.stdout.write(self.style.SUCCESS(f'\n[OK] Total exchange rates created/updated: {rate_count}'))
        self.stdout.write(self.style.SUCCESS('\n[OK] Currency population complete!'))



