window.BENCHMARK_DATA = {
  "lastUpdate": 1756934941536,
  "repoUrl": "https://github.com/zachatkinson/csfrace-scrape-back",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "committer": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "distinct": true,
          "id": "665b119d6f6f6288a9d2e75b202772e0aa0feafb",
          "message": "fix(ci): preserve benchmark.json for github-action-benchmark\n\n- Use git commit instead of git stash to handle uncommitted changes\n- Ensures benchmark.json remains available for github-action-benchmark\n- Fixes 'Unexpected end of JSON input' error in benchmark action\n- Temporary commit approach prevents git conflicts during branch switching\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
          "timestamp": "2025-09-03T06:54:22-04:00",
          "tree_id": "eb1669918d17dfcc653ecc331b476667a6d571ca",
          "url": "https://github.com/zachatkinson/csfrace-scrape-back/commit/665b119d6f6f6288a9d2e75b202772e0aa0feafb"
        },
        "date": 1756897311055,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_resilience_manager_concurrent_performance",
            "value": 691.0688726084036,
            "unit": "iter/sec",
            "range": "stddev: 0.000015996095629376885",
            "extra": "mean: 1.447033775701041 msec\nrounds: 535"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_session_manager_concurrent_requests",
            "value": 1061.6064821988618,
            "unit": "iter/sec",
            "range": "stddev: 0.0019190044704569087",
            "extra": "mean: 941.9686265750197 usec\nrounds: 873"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_threaded_html_processing_performance",
            "value": 0.14123981075581937,
            "unit": "iter/sec",
            "range": "stddev: 0.3557864903575334",
            "extra": "mean: 7.080156753599996 sec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_retry_mechanism_under_stress",
            "value": 366.4690225033282,
            "unit": "iter/sec",
            "range": "stddev: 0.00016765652170932065",
            "extra": "mean: 2.7287436006706907 msec\nrounds: 298"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_url_validator_performance_stress",
            "value": 57.13255317029948,
            "unit": "iter/sec",
            "range": "stddev: 0.00046842077282910734",
            "extra": "mean: 17.503156160713168 msec\nrounds: 56"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_circuit_breaker_recovery_performance",
            "value": 6.643803283153688,
            "unit": "iter/sec",
            "range": "stddev: 0.00007981066280436384",
            "extra": "mean: 150.5161964285792 msec\nrounds: 7"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_html_processor_baseline_performance",
            "value": 425.8547216958889,
            "unit": "iter/sec",
            "range": "stddev: 0.0005917209830855981",
            "extra": "mean: 2.3482186507588367 msec\nrounds: 13704"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_session_config_creation_performance",
            "value": 421742.3548513233,
            "unit": "iter/sec",
            "range": "stddev: 4.0801944191380186e-7",
            "extra": "mean: 2.371115892195674 usec\nrounds: 1193247"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_retry_config_delay_calculation_performance",
            "value": 41207.202746258925,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015030433429069914",
            "extra": "mean: 24.267602102420962 usec\nrounds: 295189"
          },
          {
            "name": "tests/performance/test_caching_performance.py::TestCachePerformance::test_simple_cache_benchmark",
            "value": 582.7801667022446,
            "unit": "iter/sec",
            "range": "stddev: 0.00004471127159074701",
            "extra": "mean: 1.7159128898614735 msec\nrounds: 572"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_large_content",
            "value": 8.775760093154107,
            "unit": "iter/sec",
            "range": "stddev: 0.02637859726179827",
            "extra": "mean: 113.95024355555152 msec\nrounds: 9"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_complex_content",
            "value": 160.9875112059898,
            "unit": "iter/sec",
            "range": "stddev: 0.000254809012063601",
            "extra": "mean: 6.2116619637684884 msec\nrounds: 138"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_metadata_extraction_performance",
            "value": 49.265329592143424,
            "unit": "iter/sec",
            "range": "stddev: 0.0002528465641764396",
            "extra": "mean: 20.298250479166075 msec\nrounds: 48"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_concurrent_processing_performance",
            "value": 96.03778332103965,
            "unit": "iter/sec",
            "range": "stddev: 0.0002545723019290399",
            "extra": "mean: 10.412568526880221 msec\nrounds: 93"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_memory_efficiency_large_content",
            "value": 9.503289914635326,
            "unit": "iter/sec",
            "range": "stddev: 0.000522112062761241",
            "extra": "mean: 105.22671716664907 msec\nrounds: 6"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_soup_parsing_performance",
            "value": 69.51952839807973,
            "unit": "iter/sec",
            "range": "stddev: 0.01270905159963187",
            "extra": "mean: 14.384447406976685 msec\nrounds: 86"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_processing_scalability",
            "value": 4.924176035531336,
            "unit": "iter/sec",
            "range": "stddev: 0.03536261732593119",
            "extra": "mean: 203.0796609999944 msec\nrounds: 6"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark",
            "value": 1005.494491253393,
            "unit": "iter/sec",
            "range": "stddev: 0.00008347499119517996",
            "extra": "mean: 994.5355332115805 usec\nrounds: 542"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.446240026777804,
            "unit": "iter/sec",
            "range": "stddev: 0.0032499841616959657",
            "extra": "mean: 105.86222636363698 msec\nrounds: 11"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_concurrent_detection_benchmark",
            "value": 139.2619397858033,
            "unit": "iter/sec",
            "range": "stddev: 0.0003341831177731394",
            "extra": "mean: 7.180712846152259 msec\nrounds: 130"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestBrowserSpecificPerformance::test_browser_config_creation_performance",
            "value": 382811.5587783842,
            "unit": "iter/sec",
            "range": "stddev: 6.503817204313606e-7",
            "extra": "mean: 2.6122513207050684 usec\nrounds: 59060"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestResourceLimitPerformance::test_cpu_intensive_content_detection",
            "value": 4.447452756835448,
            "unit": "iter/sec",
            "range": "stddev: 0.00039180549250361055",
            "extra": "mean: 224.8478071999898 msec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.56086904155378,
            "unit": "iter/sec",
            "range": "stddev: 0.00584523612053766",
            "extra": "mean: 104.59300254545538 msec\nrounds: 11"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark_various_sizes",
            "value": 716.9624733226245,
            "unit": "iter/sec",
            "range": "stddev: 0.0001834840733018964",
            "extra": "mean: 1.3947731397512235 msec\nrounds: 644"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_config_creation_performance",
            "value": 368466.1354631869,
            "unit": "iter/sec",
            "range": "stddev: 5.095058512099203e-7",
            "extra": "mean: 2.713953614062612 usec\nrounds: 31281"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_pool_creation_performance",
            "value": 444591.4231125747,
            "unit": "iter/sec",
            "range": "stddev: 4.152150382223604e-7",
            "extra": "mean: 2.249256166479826 usec\nrounds: 72328"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_cpu_intensive_content_detection",
            "value": 7.520216242464553,
            "unit": "iter/sec",
            "range": "stddev: 0.003903205049741288",
            "extra": "mean: 132.97489962499753 msec\nrounds: 8"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_concurrent_content_analysis_performance",
            "value": 48.137977934284734,
            "unit": "iter/sec",
            "range": "stddev: 0.0003721862502195662",
            "extra": "mean: 20.773618729169385 msec\nrounds: 48"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "committer": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "distinct": true,
          "id": "ff185926048313b71db7eabc2e53522980b8fdb0",
          "message": "fix(release): correct workflow trigger name for semantic release\n\n- Change workflow name from 'CI/CD Pipeline' to 'Progressive CI/CD Pipeline'\n- Matches actual workflow name in ci.yml\n- Enables semantic release to trigger properly after successful CI runs\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
          "timestamp": "2025-09-03T07:49:43-04:00",
          "tree_id": "4639d81d3b727c43e5059065f728b09ebdb4bf23",
          "url": "https://github.com/zachatkinson/csfrace-scrape-back/commit/ff185926048313b71db7eabc2e53522980b8fdb0"
        },
        "date": 1756900692760,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_resilience_manager_concurrent_performance",
            "value": 674.1058118797043,
            "unit": "iter/sec",
            "range": "stddev: 0.000021726949062204762",
            "extra": "mean: 1.4834466375709754 msec\nrounds: 527"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_session_manager_concurrent_requests",
            "value": 1050.4436978226138,
            "unit": "iter/sec",
            "range": "stddev: 0.0022782732056528554",
            "extra": "mean: 951.9786753662526 usec\nrounds: 881"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_threaded_html_processing_performance",
            "value": 0.13230500783444193,
            "unit": "iter/sec",
            "range": "stddev: 0.27919467845120927",
            "extra": "mean: 7.558292889800032 sec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_retry_mechanism_under_stress",
            "value": 381.4796290052294,
            "unit": "iter/sec",
            "range": "stddev: 0.00016959416592643727",
            "extra": "mean: 2.6213719526981394 msec\nrounds: 296"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_url_validator_performance_stress",
            "value": 59.2346030789074,
            "unit": "iter/sec",
            "range": "stddev: 0.0004941701024778893",
            "extra": "mean: 16.88202415516963 msec\nrounds: 58"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_circuit_breaker_recovery_performance",
            "value": 6.639094381243537,
            "unit": "iter/sec",
            "range": "stddev: 0.00008924161150007925",
            "extra": "mean: 150.62295285711767 msec\nrounds: 7"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_html_processor_baseline_performance",
            "value": 426.1951009022227,
            "unit": "iter/sec",
            "range": "stddev: 0.0007446718864436848",
            "extra": "mean: 2.346343254258615 msec\nrounds: 13793"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_session_config_creation_performance",
            "value": 423486.53624360374,
            "unit": "iter/sec",
            "range": "stddev: 4.1148823052747894e-7",
            "extra": "mean: 2.361350159724479 usec\nrounds: 1118381"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_retry_config_delay_calculation_performance",
            "value": 41835.87613628776,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018025793763545869",
            "extra": "mean: 23.902929551237868 usec\nrounds: 276442"
          },
          {
            "name": "tests/performance/test_caching_performance.py::TestCachePerformance::test_simple_cache_benchmark",
            "value": 574.9739288185748,
            "unit": "iter/sec",
            "range": "stddev: 0.0000645672164365207",
            "extra": "mean: 1.7392092925930498 msec\nrounds: 540"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_large_content",
            "value": 8.601792096332279,
            "unit": "iter/sec",
            "range": "stddev: 0.030052613447222626",
            "extra": "mean: 116.25484420001158 msec\nrounds: 10"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_complex_content",
            "value": 142.12392089958905,
            "unit": "iter/sec",
            "range": "stddev: 0.008858444836407168",
            "extra": "mean: 7.036113229007402 msec\nrounds: 131"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_metadata_extraction_performance",
            "value": 47.64151673845302,
            "unit": "iter/sec",
            "range": "stddev: 0.00008400738947882781",
            "extra": "mean: 20.990095791657854 msec\nrounds: 48"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_concurrent_processing_performance",
            "value": 95.0424858659725,
            "unit": "iter/sec",
            "range": "stddev: 0.0003078202218566934",
            "extra": "mean: 10.521610318675641 msec\nrounds: 91"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_memory_efficiency_large_content",
            "value": 8.573415450659885,
            "unit": "iter/sec",
            "range": "stddev: 0.028002225041747243",
            "extra": "mean: 116.63962930001617 msec\nrounds: 10"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_soup_parsing_performance",
            "value": 69.7570176757912,
            "unit": "iter/sec",
            "range": "stddev: 0.015525934868056545",
            "extra": "mean: 14.335475244192452 msec\nrounds: 86"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_processing_scalability",
            "value": 4.821794243819876,
            "unit": "iter/sec",
            "range": "stddev: 0.040825519943702954",
            "extra": "mean: 207.39167816662984 msec\nrounds: 6"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark",
            "value": 1013.1598434120294,
            "unit": "iter/sec",
            "range": "stddev: 0.00007715748869058581",
            "extra": "mean: 987.0110886277224 usec\nrounds: 519"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.502811699700503,
            "unit": "iter/sec",
            "range": "stddev: 0.007412038656843701",
            "extra": "mean: 105.23201254545711 msec\nrounds: 11"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_concurrent_detection_benchmark",
            "value": 139.21707850298495,
            "unit": "iter/sec",
            "range": "stddev: 0.0002808216158102868",
            "extra": "mean: 7.183026757586779 msec\nrounds: 132"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestBrowserSpecificPerformance::test_browser_config_creation_performance",
            "value": 384382.68971944705,
            "unit": "iter/sec",
            "range": "stddev: 4.586250895554655e-7",
            "extra": "mean: 2.601573969758834 usec\nrounds: 48736"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestResourceLimitPerformance::test_cpu_intensive_content_detection",
            "value": 4.373022660182744,
            "unit": "iter/sec",
            "range": "stddev: 0.000760195032809358",
            "extra": "mean: 228.6747812000158 msec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.259638475749085,
            "unit": "iter/sec",
            "range": "stddev: 0.005922487885246682",
            "extra": "mean: 107.99557700000832 msec\nrounds: 10"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark_various_sizes",
            "value": 714.6936370689062,
            "unit": "iter/sec",
            "range": "stddev: 0.00016222536431437066",
            "extra": "mean: 1.3992009276886654 msec\nrounds: 650"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_config_creation_performance",
            "value": 378847.9688400269,
            "unit": "iter/sec",
            "range": "stddev: 4.6323170729078805e-7",
            "extra": "mean: 2.6395812628000708 usec\nrounds: 36099"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_pool_creation_performance",
            "value": 445096.5426000488,
            "unit": "iter/sec",
            "range": "stddev: 4.3661558527551756e-7",
            "extra": "mean: 2.24670358964925 usec\nrounds: 65885"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_cpu_intensive_content_detection",
            "value": 7.4568711050305065,
            "unit": "iter/sec",
            "range": "stddev: 0.0027215937898617754",
            "extra": "mean: 134.10450387500816 msec\nrounds: 8"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_concurrent_content_analysis_performance",
            "value": 48.17493929501701,
            "unit": "iter/sec",
            "range": "stddev: 0.0004060176092450542",
            "extra": "mean: 20.757680541663603 msec\nrounds: 48"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "committer": {
            "email": "zach.atkinson85@gmail.com",
            "name": "zachatkinson",
            "username": "zachatkinson"
          },
          "distinct": true,
          "id": "555b30c27ed1365fd3da748a3514eebdf2cbfd1d",
          "message": "fix(api): update root endpoint to use dynamic version from package\n\n- Fixed hardcoded \"1.1.0\" in root endpoint to use __version__ import\n- Ensures root endpoint returns current package version automatically\n- Completes version assertion fix across all API endpoints\n- Resolves CI test failure: AssertionError: assert '1.1.0' == '2.0.0'\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
          "timestamp": "2025-09-03T17:20:21-04:00",
          "tree_id": "22b5ec996a81615f953b3d6fe1a5bc92ab6edee9",
          "url": "https://github.com/zachatkinson/csfrace-scrape-back/commit/555b30c27ed1365fd3da748a3514eebdf2cbfd1d"
        },
        "date": 1756934941202,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_resilience_manager_concurrent_performance",
            "value": 691.3472390421107,
            "unit": "iter/sec",
            "range": "stddev: 0.000015413296006926066",
            "extra": "mean: 1.4464511370372146 msec\nrounds: 540"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_session_manager_concurrent_requests",
            "value": 1073.1117271303783,
            "unit": "iter/sec",
            "range": "stddev: 0.001927557112527914",
            "extra": "mean: 931.8694174315964 usec\nrounds: 872"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestConcurrencyPerformance::test_threaded_html_processing_performance",
            "value": 0.13705732273218507,
            "unit": "iter/sec",
            "range": "stddev: 0.1105909065977665",
            "extra": "mean: 7.296217232800001 sec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_retry_mechanism_under_stress",
            "value": 377.0636279752156,
            "unit": "iter/sec",
            "range": "stddev: 0.00014161474662681696",
            "extra": "mean: 2.6520722918035733 msec\nrounds: 305"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_url_validator_performance_stress",
            "value": 58.445188794614026,
            "unit": "iter/sec",
            "range": "stddev: 0.0005029828162917227",
            "extra": "mean: 17.110048245616316 msec\nrounds: 57"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceBoundaries::test_circuit_breaker_recovery_performance",
            "value": 6.642709456650326,
            "unit": "iter/sec",
            "range": "stddev: 0.00006262477337740624",
            "extra": "mean: 150.54098128570917 msec\nrounds: 7"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_html_processor_baseline_performance",
            "value": 426.6125056093249,
            "unit": "iter/sec",
            "range": "stddev: 0.0005971757434815561",
            "extra": "mean: 2.3440475533451917 msec\nrounds: 13572"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_session_config_creation_performance",
            "value": 422917.4739241901,
            "unit": "iter/sec",
            "range": "stddev: 4.039229920931122e-7",
            "extra": "mean: 2.3645275063268123 usec\nrounds: 1116508"
          },
          {
            "name": "tests/performance/test_benchmarks.py::TestPerformanceRegression::test_retry_config_delay_calculation_performance",
            "value": 41226.66154165794,
            "unit": "iter/sec",
            "range": "stddev: 0.0000014974123655239273",
            "extra": "mean: 24.256147905392215 usec\nrounds: 287258"
          },
          {
            "name": "tests/performance/test_caching_performance.py::TestCachePerformance::test_simple_cache_benchmark",
            "value": 569.111611529703,
            "unit": "iter/sec",
            "range": "stddev: 0.00005223235939237929",
            "extra": "mean: 1.7571245775712099 msec\nrounds: 535"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_large_content",
            "value": 8.641280477383477,
            "unit": "iter/sec",
            "range": "stddev: 0.02763121865193127",
            "extra": "mean: 115.72359011112592 msec\nrounds: 9"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_html_processor_performance_complex_content",
            "value": 159.2469774148857,
            "unit": "iter/sec",
            "range": "stddev: 0.000329294941248078",
            "extra": "mean: 6.279554037592204 msec\nrounds: 133"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_metadata_extraction_performance",
            "value": 48.5348244013342,
            "unit": "iter/sec",
            "range": "stddev: 0.00007175629134860813",
            "extra": "mean: 20.60376260416656 msec\nrounds: 48"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_concurrent_processing_performance",
            "value": 95.23959600953384,
            "unit": "iter/sec",
            "range": "stddev: 0.0003279736127324376",
            "extra": "mean: 10.499834542556188 msec\nrounds: 94"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_memory_efficiency_large_content",
            "value": 8.712410078017513,
            "unit": "iter/sec",
            "range": "stddev: 0.026992277120712185",
            "extra": "mean: 114.77880300000152 msec\nrounds: 10"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_soup_parsing_performance",
            "value": 72.00874571543974,
            "unit": "iter/sec",
            "range": "stddev: 0.013546351993914548",
            "extra": "mean: 13.88720203448267 msec\nrounds: 87"
          },
          {
            "name": "tests/performance/test_html_processing_performance.py::TestHTMLProcessingPerformance::test_processing_scalability",
            "value": 5.237194623672556,
            "unit": "iter/sec",
            "range": "stddev: 0.0008691821510596115",
            "extra": "mean: 190.94192059999386 msec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark",
            "value": 1008.9733754364553,
            "unit": "iter/sec",
            "range": "stddev: 0.00006771428378262256",
            "extra": "mean: 991.1064299069601 usec\nrounds: 535"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.338390619706784,
            "unit": "iter/sec",
            "range": "stddev: 0.0023139757248754485",
            "extra": "mean: 107.08483299999277 msec\nrounds: 11"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestRenderingPerformanceBenchmarks::test_concurrent_detection_benchmark",
            "value": 141.30484922525702,
            "unit": "iter/sec",
            "range": "stddev: 0.00015628883875961068",
            "extra": "mean: 7.076897965517652 msec\nrounds: 87"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestBrowserSpecificPerformance::test_browser_config_creation_performance",
            "value": 374300.50955721724,
            "unit": "iter/sec",
            "range": "stddev: 4.986523784658476e-7",
            "extra": "mean: 2.6716501165947135 usec\nrounds: 61309"
          },
          {
            "name": "tests/performance/test_rendering_benchmarks.py::TestResourceLimitPerformance::test_cpu_intensive_content_detection",
            "value": 4.414709585954118,
            "unit": "iter/sec",
            "range": "stddev: 0.0014488374497154744",
            "extra": "mean: 226.51546619999863 msec\nrounds: 5"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_large_content_handling_performance",
            "value": 9.337206320500215,
            "unit": "iter/sec",
            "range": "stddev: 0.005220950239482826",
            "extra": "mean: 107.09841527272022 msec\nrounds: 11"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestRenderingPerformanceBenchmarks::test_content_detector_speed_benchmark_various_sizes",
            "value": 720.6761926373784,
            "unit": "iter/sec",
            "range": "stddev: 0.0001639099544183169",
            "extra": "mean: 1.387585728814506 msec\nrounds: 649"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_config_creation_performance",
            "value": 366760.87152318005,
            "unit": "iter/sec",
            "range": "stddev: 6.748109153149278e-7",
            "extra": "mean: 2.726572209971417 usec\nrounds: 35660"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestBrowserConfigPerformance::test_browser_pool_creation_performance",
            "value": 438289.93437307497,
            "unit": "iter/sec",
            "range": "stddev: 4.3455168276010386e-7",
            "extra": "mean: 2.281594719783809 usec\nrounds: 33293"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_cpu_intensive_content_detection",
            "value": 7.5372473238650475,
            "unit": "iter/sec",
            "range": "stddev: 0.001432965741067293",
            "extra": "mean: 132.674430999991 msec\nrounds: 8"
          },
          {
            "name": "tests/performance/test_rendering_performance.py::TestContentDetectionStress::test_concurrent_content_analysis_performance",
            "value": 48.1754325236799,
            "unit": "iter/sec",
            "range": "stddev: 0.00034461868048792365",
            "extra": "mean: 20.757468020831265 msec\nrounds: 48"
          }
        ]
      }
    ]
  }
}