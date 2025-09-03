window.BENCHMARK_DATA = {
  "lastUpdate": 1756897311968,
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
      }
    ]
  }
}