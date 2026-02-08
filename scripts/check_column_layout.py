#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time

BASE_URL = "http://localhost"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Load the main dashboard
    page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
    time.sleep(1)

    # Enable Column View
    try:
        # Wait for page to load
        page.wait_for_selector('#rounds', timeout=5000)
        time.sleep(0.5)

        # Enable column view by adding the class directly
        page.evaluate("""
            () => {
                document.querySelector('#rounds').classList.add('usecolumns');
                document.querySelector('#allrounds').classList.add('usecolumns');
            }
        """)
        time.sleep(0.5)
    except Exception as e:
        print(f"Could not enable Column View: {e}")
        browser.close()
        exit(1)

    print("=" * 80)
    print("COLUMN VIEW LAYOUT ANALYSIS")
    print("=" * 80)

    # Get all round elements
    rounds = page.locator('#rounds.usecolumns .round').all()

    if len(rounds) == 0:
        print("No rounds found!")
        browser.close()
        exit(1)

    print(f"\nFound {len(rounds)} rounds\n")

    # Get the #rounds container info
    container_info = page.evaluate("""
        () => {
            const container = document.querySelector('#rounds.usecolumns');
            const computed = window.getComputedStyle(container);
            const rect = container.getBoundingClientRect();
            return {
                gap: computed.gap,
                paddingLeft: computed.paddingLeft,
                paddingRight: computed.paddingRight,
                width: rect.width,
                scrollWidth: container.scrollWidth
            };
        }
    """)

    print("Container (#rounds.usecolumns):")
    print(f"  gap: {container_info['gap']}")
    print(f"  paddingLeft: {container_info['paddingLeft']}")
    print(f"  paddingRight: {container_info['paddingRight']}")
    print(f"  visible width: {container_info['width']:.1f}px")
    print(f"  scroll width: {container_info['scrollWidth']:.1f}px")
    print()

    # Measure each round
    round_positions = []
    for i in range(min(5, len(rounds))):  # Check first 5 rounds
        info = page.evaluate(f"""
            () => {{
                const round = document.querySelectorAll('#rounds.usecolumns .round')[{i}];
                const rect = round.getBoundingClientRect();
                const computed = window.getComputedStyle(round);

                // Check for any overflow
                const hasOverflow = round.scrollWidth > round.clientWidth ||
                                   round.scrollHeight > round.clientHeight;

                return {{
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    left: rect.left,
                    right: rect.right,
                    minWidth: computed.minWidth,
                    maxWidth: computed.maxWidth,
                    marginLeft: computed.marginLeft,
                    marginRight: computed.marginRight,
                    scrollWidth: round.scrollWidth,
                    clientWidth: round.clientWidth,
                    hasOverflow: hasOverflow
                }};
            }}
        """)
        round_positions.append(info)

        print(f"Round {i}:")
        print(f"  position: x={info['left']:.1f}, y={info['y']:.1f}")
        print(f"  dimensions: {info['width']:.1f}px × {info['height']:.1f}px")
        print(f"  right edge: {info['right']:.1f}px")
        print(f"  minWidth: {info['minWidth']}, maxWidth: {info['maxWidth']}")
        print(f"  scrollWidth: {info['scrollWidth']}, clientWidth: {info['clientWidth']}")
        print(f"  overflow: {info['hasOverflow']}")

        if i > 0:
            gap = round_positions[i]['left'] - round_positions[i-1]['right']
            print(f"  gap from previous round: {gap:.1f}px")

        print()

    # Check if any round-header content is overflowing
    print("\n" + "=" * 80)
    print("ROUND HEADER OVERFLOW CHECK")
    print("=" * 80)

    for i in range(min(3, len(rounds))):
        overflow_info = page.evaluate(f"""
            () => {{
                const round = document.querySelectorAll('#rounds.usecolumns .round')[{i}];
                const header = round.querySelector('.round-header');
                if (!header) return null;

                const headerRect = header.getBoundingClientRect();
                const roundRect = round.getBoundingClientRect();

                // Check all children
                const children = Array.from(header.children);
                const childrenInfo = children.map(child => {{
                    const rect = child.getBoundingClientRect();
                    return {{
                        tag: child.tagName,
                        className: child.className,
                        right: rect.right,
                        exceedsParent: rect.right > headerRect.right
                    }};
                }});

                return {{
                    headerRight: headerRect.right,
                    roundRight: roundRect.right,
                    headerExceedsRound: headerRect.right > roundRect.right,
                    children: childrenInfo
                }};
            }}
        """)

        if overflow_info:
            print(f"\nRound {i} header:")
            print(f"  header right edge: {overflow_info['headerRight']:.1f}px")
            print(f"  round right edge: {overflow_info['roundRight']:.1f}px")
            print(f"  header exceeds round: {overflow_info['headerExceedsRound']}")

            for child in overflow_info['children']:
                if child['exceedsParent']:
                    print(f"  ⚠️  {child['tag']}.{child['className']} exceeds header (right: {child['right']:.1f}px)")

    browser.close()
