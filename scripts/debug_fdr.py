import FinanceDataReader as fdr

def test_fdr():
    print("Testing FinanceDataReader for KRX Stock Listing...")
    try:
        df_krx = fdr.StockListing('KRX')
        print(f"KRX Stock Listing Count: {len(df_krx)}")
        print(df_krx.head())
    except Exception as e:
        print(f"Error fetching using FDR: {e}")

if __name__ == "__main__":
    test_fdr()
