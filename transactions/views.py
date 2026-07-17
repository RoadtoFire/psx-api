from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Portfolio, Transaction, PurificationRecord
from .serializers import PortfolioSerializer, TransactionSerializer
from .calculators import calculate_dividend_income, calculate_portfolio_value
from .importers import parse_import_file




class PortfolioView(generics.RetrieveAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=self.request.user,
            defaults={'name': 'My Portfolio'}
        )
        return portfolio


class TransactionCreateView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=self.request.user,
            defaults={'name': 'My Portfolio'}
        )
        serializer.save(portfolio=portfolio)


class TransactionDeleteView(generics.DestroyAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        )
    

class DividendIncomeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )

        results = calculate_dividend_income(
            portfolio=portfolio,
            tax_rate=request.user.tax_rate
        )

        # Summary totals
        total_gross = sum(r['gross_dividend'] for r in results)
        total_tax = sum(r['tax_deducted'] for r in results)
        total_purification = sum(r['purification_amount'] for r in results)
        total_net = sum(r['final_amount'] for r in results)

        return Response({
            'summary': {
                'total_gross': round(total_gross, 2),
                'total_tax_deducted': round(total_tax, 2),
                'total_purification': round(total_purification, 2),
                'total_net': round(total_net, 2),
                'filer_status': request.user.filer_status,
                'tax_rate': request.user.tax_rate,
            },
            'dividends': results
        })
    
class PortfolioValueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )
        data = calculate_portfolio_value(portfolio)
        return Response(data)
    

class MarkPurifiedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from datetime import date
        from decimal import Decimal

        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )

        amount = request.data.get('amount', 0)
        purified_up_to = request.data.get('purified_up_to', str(date.today()))

        # Prevent duplicate records for same date
        record, created = PurificationRecord.objects.get_or_create(
            portfolio=portfolio,
            purified_up_to_date=purified_up_to,
            defaults={'amount_purified': Decimal(str(amount))}
        )

        if not created:
            # Update amount if already exists
            record.amount_purified = Decimal(str(amount))
            record.save()

        return Response({'status': 'purified', 'amount': float(record.amount_purified)})

class PurificationHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'}
        )

        records = PurificationRecord.objects.filter(portfolio=portfolio)
        total_purified = sum(r.amount_purified for r in records)
        latest = records.first()

        return Response({
            'total_purified': float(total_purified),
            'latest_purification_date': str(latest.purified_up_to_date) if latest else None,
            'records': [
                {
                    'date': str(r.created_at.date()),
                    'purified_up_to': str(r.purified_up_to_date),
                    'amount': float(r.amount_purified)
                }
                for r in records
            ]
        })


class TransactionImportView(APIView):
    """
    POST /api/v1/portfolio/transactions/import/
    Accepts a multipart file upload (.csv / .xlsx / .png / .jpg / .jpeg).
    Returns a preview of parsed rows without saving anything.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file_bytes = file.read()
        filename = file.name or 'upload'
        api_key = getattr(settings, 'GEMINI_API_KEY', '')

        raw_rows, error = parse_import_file(file_bytes, filename, api_key)
        if error:
            return Response({'error': error}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not raw_rows:
            return Response(
                {'parsed': [], 'skipped': [], 'message': 'No transaction rows found in the file.'},
                status=status.HTTP_200_OK,
            )

        parsed = []
        skipped = []

        for i, row in enumerate(raw_rows):
            ser = TransactionSerializer(data=row)
            if ser.is_valid():
                # Return the validated display values (don't save yet)
                vd = ser.validated_data
                parsed.append({
                    'stock_symbol':     vd['stock_symbol'].symbol,
                    'date':             str(vd['date']),
                    'transaction_type': vd['transaction_type'],
                    'shares':           str(vd['shares']),
                    'price_per_share':  str(vd['price_per_share']),
                })
            else:
                skipped.append({
                    'row':    i + 1,
                    'data':   row,
                    'reason': '; '.join(
                        f"{f}: {', '.join(e)}" for f, e in ser.errors.items()
                    ),
                })

        return Response({'parsed': parsed, 'skipped': skipped})


class TransactionBulkConfirmView(APIView):
    """
    POST /api/v1/portfolio/transactions/import/confirm/
    Body: { "transactions": [{stock_symbol, date, transaction_type, shares, price_per_share}, ...] }
    Validates and bulk-creates the confirmed rows for the authenticated user's portfolio.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        rows = request.data.get('transactions', [])
        if not isinstance(rows, list) or not rows:
            return Response(
                {'error': 'transactions must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        portfolio, _ = Portfolio.objects.get_or_create(
            user=request.user,
            defaults={'name': 'My Portfolio'},
        )

        created = 0
        failed = []

        for i, row in enumerate(rows):
            ser = TransactionSerializer(data=row)
            if ser.is_valid():
                ser.save(portfolio=portfolio)
                created += 1
            else:
                failed.append({
                    'row':    i + 1,
                    'data':   row,
                    'reason': '; '.join(
                        f"{f}: {', '.join(e)}" for f, e in ser.errors.items()
                    ),
                })

        return Response({'created': created, 'failed': failed})