import FinanceDataReader as fdr

def test_fdr():
    print("Testing FinanceDataReader for KRX Stock Listing...")
    try:
        df_krx = fdr.StockListing('KRX')
        print(f"KRX Stock Listing Count: {len(df_krx)}")
        print("Columns:", df_krx.columns.tolist())
        if not df_krx.empty:
            print("First Row:", df_krx.iloc[0].to_dict())
    except Exception as e:
        print(f"Error fetching using FDR (KRX): {e}")

    print("\nTesting FinanceDataReader for KOSPI Stock Listing...")
    try:
        df_kospi = fdr.StockListing('KOSPI')
        print("Columns (KOSPI):", df_kospi.columns.tolist())
        if not df_kospi.empty:
            print("First Row (KOSPI):", df_kospi.iloc[0].to_dict())
    except Exception as e:
        print(f"Error fetching using FDR (KOSPI): {e}")

    print("\nTesting FinanceDataReader for KRX-DESC...")
    try:
        df_desc = fdr.StockListing('KRX-DESC')
        print("Columns (KRX-DESC):", df_desc.columns.tolist())
        if not df_desc.empty:
            print("First Row (KRX-DESC):", df_desc.iloc[0].to_dict())
    except Exception as e:
        print(f"Error fetching using FDR (KRX-DESC): {e}")


if __name__ == "__main__":
    print("Testing FinanceDataReader for KRX-DESC...")
    try:
        df_desc = fdr.StockListing('KRX-DESC')
        print(f"KRX-DESC Count: {len(df_desc)}")
        print("Columns:", df_desc.columns.tolist())
        if not df_desc.empty:
            print("First Row:", df_desc.iloc[0].to_dict())
            
        # Check Samsung Electronics (005930)
        samsung = df_desc[df_desc['Code'] == '005930']
        if not samsung.empty:
            print("Samsung Data:", samsung.iloc[0].to_dict())
        else:
            print("Samsung not found in KRX-DESC")
            
    except Exception as e:
        print(f"Error fetching using FDR (KRX-DESC): {e}")
