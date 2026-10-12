import asyncio

from app.services.rate_limit import LocalRateLimiter, positive_int_setting


def test_limit_30_and_retry_after():
    async def check():
        limiter = LocalRateLimiter(per_minute=30)
        for _ in range(30):
            allowed, retry = await limiter.check('local')
            assert allowed and retry == 0
        allowed, retry = await limiter.check('local')
        assert not allowed and 1 <= retry <= 60
        allowed_other, _ = await limiter.check('other')
        assert allowed_other
    asyncio.run(check())


def test_allow_backwards_compatible():
    async def check():
        limiter = LocalRateLimiter(per_minute=1)
        assert await limiter.allow('x')
        assert not await limiter.allow('x')
    asyncio.run(check())
