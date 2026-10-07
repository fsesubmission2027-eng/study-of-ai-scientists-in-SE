# README


## Datasets

### widelyUsedPackages.csv
Dataset containing the 28,100 widely-used npm packages identified (See Sec. IV)
####  Variables: 
- npmPackageName: Name of package in npm registry
- slug: GitHub slug associated with package 
- isAbandoned: binary flag representing whether we identified the package as abandoned during our observation window
- repoArchived: binary flag representing whether we identified the package's repository as being archived during our observation window
- READMEKeyword: binary flag representing whether we identified the package's repository README as containing an abandonment announcement during our observation window
- READMEBadge: binary flag repreenting whether we identified the package's repository README as containing the `no maintenance intended`  badge during our observation window
- activityBasedAbandoned: binary flag representing whether we identified the package as becoming activity-based abandoned during our observation window
- maxNumDownloads: The peak monthly download counts for the package during our observation window 
- numStars: The current number of stars for package (as of March 2024)



### abandonmentExposedDependentsData.csv
Dataset containing the 2,288 projects we identified as being directly exposed to dependency abandonment (See Sec. IV) and the additional data collected for each project for modeling (See Sec. VI)
#### Variables: 
- repo - GitHub repo slug for dependent project
- dependency - Name of the npm package the project was identified as depending on 
- dependencyType - The type of the dependency ('dependency', 'devDependency', 'peerDependency')
- depAbandonedAt - The date when the dependency was identified as being abandoned
- monthsFromAbandonmentToRemoval - Elapsed time from abandonment to removal in months 
- abandonmentTypeBinary - Binary flag for the type of dependency abandonment ('explicit-notice','activity-based'), note if dependency met both abandonment definitions we considered it explicit-notice
- statusEver: 
#### Factors Collected For Modeling (See Sec. VI for operationalization details): 
- repoAgeAtAbandonment - Repo age in months at the time of depenency abandonment 
- totalNumDependencies - Total number of dependencies at the time of depenency abandonment 
- numNormalDeps - number of standard dependencies at the time of depenency abandonment
- numDevDeps - Number of dev dependencies at the time of depenency abandonment
- totalDependencyChurn - Total dependency chrun in the year before depenency abandonemnt
- repoSize - Repo size in bytes at the time of depenency abandonment
- numCommits - Total number of commits in the year before depenency abandonemnt
- numMaintainers - Number of project maintainers in the year before depenency abandonemnt
- numCorporateCommits - Number of commits from corporate contributors in the year before depenency abandonemnt
- useDepManagementTools - Binary flag representing whether there was use of dependency management tool usage in the year before dependency abandonment
- hasCoC - Binary flag representing whether project had code of conduct at time of dependency abandonment
- hasContributing - Binary flag representing whether project had CONTRIBUTING doc at time of dependency abandonment
- hasLicense - Binary flag representing whether project had license at time of dependency abandonment
- hasIssueTemplate - Binary flag representing whether project had issue template at time of dependency abandonment
- hasPRTemplate - Binary flag representing whether project had PR template at time of dependency abandonment
- hasREADME - Binary flag representing whether project had README at time of dependency abandonment
- numREADMEHeaders - Number of README headers at time of dependency abandonment 
- avgTechnicalLagDays - average technical lag at time of depenency abandonment (excluding abandoned dependency)
- medianTechnicalLagDays - median technical lag at time of depenency abandonment (excluding abandoned dependency)
- hasTechnicalLag - Binary flag representing whether the project had any technical lag at the time of dependency abandonment 
- latestCommit - The month of the latest recorded commit in the repo (as of September 2023)
- numStarsCurrent - Number of stars for the package (as of September 2023)
- numIssuesOpened - Number of issues opened in year before abandonment
- numIssuesClosed - Number of issues closed in year before abandonment



### UpdateExposedDependentsData.csv
Dataset containing the 11,925 dependent projects identified in RQ2b, note this dataset includes the subset of dependents who used floating declarations to automatically update which we exclude from our primary analysis but include here for comparitive explorations (See Sec. V).
#### Variables: 
- repo - GitHub repo slug for dependent project
- dependency - Name of the npm package the project was identified as depending on 
- dependencyVOI - The dependency version of interest we observed the response to 
- dependencyVOIDateTime - The date when the dependencyVOI was released
- updateLagHrs - The lag in time to update in hours (value of -1 if they did not update during our observation window)
- updateLagMonths The lag in time to update in months (value of -1 if they did not update during our observation window)
- depRemoved - Commit sha of commit used to remove dependency (if they did so during our observation window)
- versionRemovedDateTime - Date when commit removing dependency was made (if they do so during our observation window)
- baselineVersionFloating - Binary flag representing whether they were identified as using a floating declaration for the dependency at the time of dependencyVOI release
- latestCommit - The month of the latest recorded commit in the repo (as of September 2023)




### vulnerabilityExposedDependentsData.csv
Dataset containing the 13,190 dependent projects identified in RQ2c, note this dataset includes the subset of dependents who used floating declarations to automatically update which we exclude from our primary analysis but include here for comparitive explorations (See Sec. V).
#### Variables: 
- repo - GitHub repo slug for dependent project
- dependency - Name of the npm package the project was identified as depending on 
- patchVersion - The dependency version that patched the vulnerability, that observed the response to 
- patchVersionDateTime - The date when the patchVersion was released 
- updateLagHrs - The lag in time to update in hours (value of -1 if they did not update during our observation window)
- updateLagMonths The lag in time to update in months (value of -1 if they did not update during our observation window)
- depRemoved - Commit sha of commit used to remove dependency (if they did so during our observation window)
- versionRemovedDateTime - Date when commit removing dependency was made (if they do so during our observation window)
- baselineVersionFloating - Binary flag representing whether they were identified as using a floating declaration for the dependency at the time of patchVersion release
- latestCommit - The month of the latest recorded commit in the repo (as of September 2023)




## Scripts

### explorationAndModeling.Rmd 
Script containing replication code for all visualizations and models present in paper. Output of all visualization in script are stored in the `visualizations` folder










