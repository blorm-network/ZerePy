from solders.pubkey import Pubkey  # type: ignore

# Common token addresses used across the toolkit
SPL_TOKENS = {
    "USDC": Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
    "USDT": Pubkey.from_string("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"),
    "USDS": Pubkey.from_string("USDSwr9ApdHk5bvJKMjzff41FfuX8bSxdKcR81vTwcA"),
    "SOL": Pubkey.from_string("So11111111111111111111111111111111111111112"),
    "JITOSOL": Pubkey.from_string("J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
    "BSOL": Pubkey.from_string("bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1"),
    "MSOL": Pubkey.from_string("mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
    "BONK": Pubkey.from_string("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
}

DEFAULT_OPTIONS = {
    "SLIPPAGE_BPS": 300,  # Default slippage tolerance in basis points (300 = 3%)
    "TOKEN_DECIMALS": 9,  # Default number of decimals for new tokens
}

JUP_API = "https://quote-api.jup.ag/v6"

LAMPORTS_PER_SOL = 1_000_000_000
SOL_FEES = 100_000_000
